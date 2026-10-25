"""Append-only audit trail for evolutionary experiments.

Each run has a unique directory. Logs are flushed after each event. Visualization
uses Pillow and is deliberately separate from the geometric validator.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class RunRecorder:
    def __init__(self, root: str, config: dict, image_columns: int = 5):
        if image_columns < 1:
            raise ValueError("image_columns must be positive")
        from uuid import uuid4
        self.directory = Path(root) / ("run-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
        self.directory.mkdir(parents=True, exist_ok=False)
        self.images = self.directory / "generation_images"
        self.images.mkdir()
        self.columns = image_columns
        self.write("config.json", config)

    def write(self, filename: str, value: dict) -> None:
        (self.directory / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def append(self, filename: str, value: dict) -> None:
        with (self.directory / filename).open("a", encoding="utf-8") as f:
            f.write(json.dumps(value, ensure_ascii=False) + "\n")

    def image(self, generation: int, members: list[tuple[int, object]], side_cap: float) -> None:
        """One PNG with the entire selected population, including individual IDs."""
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise RuntimeError("Pillow is required for generation PNG images: pip install Pillow") from exc
        from .geometry import square_vertices
        cols = self.columns
        rows = (len(members) + cols - 1) // cols
        tile, margin, plot = 212, 28, 164
        canvas = Image.new("RGB", (cols * tile, max(1,rows) * tile), "white")
        draw = ImageDraw.Draw(canvas)
        colors = ["#5294ce","#63b391","#e1a664","#ac86c5","#cc7d83"]
        scale=plot / max(side_cap, 1e-10)
        for i,(ind_id,packing) in enumerate(members):
            x0 = (i%cols)*tile+margin
            y0 = (i//cols)*tile+margin
            draw.rectangle((x0,y0,x0+plot,y0+plot), outline="#444444", width=2)
            for j,sq in enumerate(packing.squares):
                points=[(round(x0+x*scale),round(y0+(side_cap-y)*scale)) for x,y in square_vertices(sq)]
                draw.polygon(points,fill=colors[j%len(colors)])
                draw.line(points+[points[0]], fill="#204057",width=2)
            draw.text((x0,y0+plot+5),f"id={ind_id}  L={packing.container_side:.6f}",fill="black")
        canvas.save(self.images / f"gen_{generation:03d}.png")
