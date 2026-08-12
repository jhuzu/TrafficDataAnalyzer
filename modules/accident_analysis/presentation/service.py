"""Generate accident presentations without leaking subprocess details into HTTP."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..data import AccidentDataset
from .payload_builder import build_presentation_payload
from .generator import generate_presentation, generate_traditional_presentation


PPTX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


@dataclass(frozen=True)
class PresentationVariant:
    label: str
    filename: str
    template: Path | None = None


@dataclass(frozen=True)
class GeneratedPresentation:
    content: bytes
    filename: str
    content_type: str = PPTX_CONTENT_TYPE


class AccidentPresentationService:
    """Create either accident deck variant from one shared payload contract."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.variants = {
            "modern": PresentationVariant(
                label="新式版本",
                filename="交通事故分析週報_新式版本.pptx",
            ),
            "traditional": PresentationVariant(
                label="傳統版本",
                filename="交通事故分析週報_傳統版本.pptx",
                template=(project_root or Path(__file__).resolve().parents[3]) / "modules" / "accident_analysis" / "templates" / "交通事故分析_原版樣式_自動填值模板.pptx",
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
        normalized_period = str(period).strip() or "115年1月1日至8月31日"
        with tempfile.TemporaryDirectory(prefix="traffic_ppt_") as tempdir:
            temporary_root = Path(tempdir)
            output_path = temporary_root / "traffic-accident-weekly-report.pptx"
            try:
                payload = build_presentation_payload(dataset, normalized_period)
                if variant.template:
                    if not variant.template.is_file():
                        raise ValueError(f"找不到{variant.label}模板：{variant.template.name}")
                    generate_traditional_presentation(payload, variant.template, output_path)
                else:
                    generate_presentation(payload, variant_key, output_path)
            except (ImportError, OSError) as error:
                raise ValueError("無法載入 PPTX 匯出套件。請執行 pip install -r requirements.txt。") from error
            if not output_path.is_file():
                raise ValueError("投影片生成失敗。")
            return GeneratedPresentation(content=output_path.read_bytes(), filename=variant.filename)
