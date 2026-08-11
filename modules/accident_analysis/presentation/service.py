"""Generate accident presentations without leaking subprocess details into HTTP."""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.runtime import find_node

from ..data import AccidentDataset
from .payload_builder import build_presentation_payload


PPTX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


@dataclass(frozen=True)
class PresentationVariant:
    label: str
    template: Path
    generator: Path
    filename: str


@dataclass(frozen=True)
class GeneratedPresentation:
    content: bytes
    filename: str
    content_type: str = PPTX_CONTENT_TYPE


class AccidentPresentationService:
    """Create either accident deck variant from one shared payload contract."""

    def __init__(self, project_root: Path | None = None) -> None:
        root = project_root or Path(__file__).resolve().parents[3]
        module_root = root / "modules" / "accident_analysis"
        presentation_root = module_root / "presentation"
        template_root = module_root / "templates"
        self.variants = {
            "modern": PresentationVariant(
                label="新式版本",
                template=template_root / "板橋分局交通事故分析週報_骨架自動填值模板.pptx",
                generator=presentation_root / "presentation_generator.mjs",
                filename="交通事故分析週報_新式版本.pptx",
            ),
            "traditional": PresentationVariant(
                label="傳統版本",
                template=template_root / "交通事故分析_原版樣式_自動填值模板.pptx",
                generator=presentation_root / "traditional_presentation_generator.mjs",
                filename="交通事故分析週報_傳統版本.pptx",
            ),
        }

    def generate(
        self,
        dataset: AccidentDataset,
        variant_key: str = "modern",
        period: str = "115年1月1日至8月31日",
    ) -> GeneratedPresentation:
        variant = self.variants.get(str(variant_key).strip().lower())
        if variant is None:
            raise ValueError("未知的投影片版本，請選擇新式版本或傳統版本。")
        if not variant.template.is_file():
            raise ValueError(f"找不到{variant.label}模板：{variant.template.name}")
        if not variant.generator.is_file():
            raise ValueError(f"找不到{variant.label}生成器：{variant.generator.name}")
        node = find_node()
        if node is None:
            raise ValueError("找不到 Node.js，無法生成投影片。請先安裝 Node.js 或設定 NODE_BIN。")

        normalized_period = str(period).strip() or "115年1月1日至8月31日"
        with tempfile.TemporaryDirectory(prefix="traffic_ppt_") as tempdir:
            temporary_root = Path(tempdir)
            data_path = temporary_root / "data.json"
            output_path = temporary_root / "traffic-accident-weekly-report.pptx"
            data_path.write_text(
                json.dumps(build_presentation_payload(dataset, normalized_period), ensure_ascii=False),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    str(node), str(variant.generator),
                    "--data", str(data_path),
                    "--template", str(variant.template),
                    "--output", str(output_path),
                    "--period", normalized_period,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode or not output_path.is_file():
                detail = result.stderr.strip() or result.stdout.strip() or "投影片生成失敗。"
                raise ValueError(detail)
            return GeneratedPresentation(content=output_path.read_bytes(), filename=variant.filename)
