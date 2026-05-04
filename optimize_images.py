from PIL import Image
from pathlib import Path

source_dir = Path("assets/images")
output_dir = Path("assets/images_optimized")
output_dir.mkdir(exist_ok=True)

max_size = (1200, 1200)

for image_path in source_dir.glob("*.jpg"):
    output_path = output_dir / image_path.name

    with Image.open(image_path) as img:
        img = img.convert("RGB")
        img.thumbnail(max_size)

        img.save(
            output_path,
            format="JPEG",
            quality=82,
            optimize=True,
            progressive=True,
        )

    old_size = image_path.stat().st_size / 1024
    new_size = output_path.stat().st_size / 1024

    print(f"{image_path.name}: {old_size:.1f} KB -> {new_size:.1f} KB")