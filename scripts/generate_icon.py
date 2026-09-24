#!/usr/bin/env python3
"""Generate VM-Harness adaptive icon — cute yet production-grade.

Design: Rounded shield with subtle gradient, containing a stylized "V" made of
two overlapping monitor screens (representing VMs). Color: violet/purple gradient
(#7c3aed → #a78bfa) on transparent background. Production-grade: clean edges,
proper padding, adaptive icon safe zone respected.
"""

from PIL import Image, ImageDraw, ImageFont
import math
import os

OUTPUT_DIR = r"C:\Projects\QEMU-MCP\android\app\src\main\res"

# Android adaptive icon sizes (foreground layer, 108x108 dp safe zone)
ICON_SIZES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

# Violet gradient colors
COLOR_BG_TOP = (124, 58, 237)      # #7c3aed - deep violet
COLOR_BG_BOTTOM = (167, 139, 250)  # #a78bfa - lighter violet
COLOR_FG = (255, 255, 255)         # white
COLOR_ACCENT = (233, 219, 255)     # very light violet accent
COLOR_SCREEN_BG = (20, 10, 40)     # dark purple-black for screen


def create_icon(size: int) -> Image.Image:
    """Create a VM-Harness icon at the given pixel size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    padding = int(size * 0.04)
    icon_area = size - 2 * padding

    # ── Background: rounded rectangle with gradient ──────────────────────
    # Create gradient
    gradient = Image.new("RGBA", (size, size))
    for y in range(size):
        ratio = y / size
        r = int(COLOR_BG_TOP[0] + (COLOR_BG_BOTTOM[0] - COLOR_BG_TOP[0]) * ratio)
        g = int(COLOR_BG_TOP[1] + (COLOR_BG_BOTTOM[1] - COLOR_BG_TOP[1]) * ratio)
        b = int(COLOR_BG_TOP[2] + (COLOR_BG_BOTTOM[2] - COLOR_BG_TOP[2]) * ratio)
        ImageDraw.Draw(gradient).line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Rounded rectangle mask
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    radius = int(size * 0.12)
    mask_draw.rounded_rectangle(
        [padding, padding, size - padding, size - padding],
        radius=radius,
        fill=255,
    )
    img = Image.composite(gradient, img, mask)

    # ── Shield outline (subtle) ───────────────────────────────────────────
    draw = ImageDraw.Draw(img)
    outline_width = max(1, int(size * 0.015))
    outline_color = (*COLOR_FG, 40)
    draw.rounded_rectangle(
        [padding, padding, size - padding, size - padding],
        radius=radius,
        outline=outline_color,
        width=outline_width,
    )

    # ── Two monitors forming a "V" — perfectly scaled ────────────────────
    center_x = size // 2
    center_y = size // 2
    monitor_w = int(size * 0.55)
    monitor_h = int(size * 0.42)
    monitor_offset_x = int(size * 0.14)
    monitor_offset_y = int(size * 0.03)
    corner_r = int(size * 0.025)
    border_w = max(2, int(size * 0.022))

    # Left monitor
    left_x = center_x - monitor_offset_x - monitor_w // 2
    left_y = center_y - monitor_offset_y - monitor_h // 2

    # Right monitor
    right_x = center_x + monitor_offset_x - monitor_w // 2
    right_y = center_y - monitor_offset_y - monitor_h // 2

    # Draw monitors (screen + bezel + stand)
    for mx, my in [(left_x, left_y), (right_x, right_y)]:
        # Screen with subtle gradient (lighter than bg for contrast)
        screen_pad = int(size * 0.015)
        sx1 = mx + screen_pad
        sy1 = my + screen_pad
        sx2 = mx + monitor_w - screen_pad
        sy2 = my + monitor_h - screen_pad

        # Screen background — deep blue-purple, distinct from icon bg
        screen_bg = (15, 15, 35)
        draw.rounded_rectangle(
            [sx1, sy1, sx2, sy2],
            radius=corner_r,
            fill=screen_bg,
        )

        # Screen glow effect (subtle lighter inner area)
        glow_pad = int(size * 0.04)
        draw.rounded_rectangle(
            [sx1 + glow_pad, sy1 + glow_pad,
             sx2 - glow_pad, sy2 - glow_pad],
            radius=corner_r // 2,
            fill=(25, 25, 55),
        )

        # Screen content: prominent colorful bars
        bar_x1 = sx1 + int(size * 0.045)
        bar_x2 = sx2 - int(size * 0.045)
        bar_h = max(2, int(size * 0.028))
        bar_spacing = int(size * 0.02)

        # Green bar (top — running)
        by1 = sy1 + int(size * 0.07)
        draw.rectangle(
            [bar_x1, by1, bar_x2, by1 + bar_h],
            fill=(34, 211, 120),
        )

        # Blue bar (middle — streaming)
        by2 = by1 + bar_h + bar_spacing
        draw.rectangle(
            [bar_x1, by2, bar_x2, by2 + bar_h],
            fill=(96, 190, 255),
        )

        # Purple bar (bottom — VM activity)
        by3 = by2 + bar_h + bar_spacing
        draw.rectangle(
            [bar_x1, by3, bar_x2, by3 + bar_h],
            fill=(180, 150, 255),
        )

        # Bezel border — thick white
        draw.rounded_rectangle(
            [mx, my, mx + monitor_w, my + monitor_h],
            radius=corner_r,
            outline=COLOR_FG,
            width=border_w,
        )

        # Stand (trapezoid below)
        stand_w = int(monitor_w * 0.25)
        stand_h = int(size * 0.03)
        stand_x = mx + monitor_w // 2 - stand_w // 2
        stand_y = my + monitor_h
        draw.polygon([
            (stand_x, stand_y),
            (stand_x + stand_w, stand_y),
            (stand_x + stand_w + int(size * 0.02), stand_y + stand_h),
            (stand_x - int(size * 0.02), stand_y + stand_h),
        ], fill=COLOR_FG)

        # Stand base
        base_w = int(stand_w * 1.5)
        base_x = mx + monitor_w // 2 - base_w // 2
        draw.rectangle(
            [base_x, stand_y + stand_h,
             base_x + base_w, stand_y + stand_h + int(size * 0.015)],
            fill=COLOR_FG,
        )

    # ── Connection line between monitors (streaming link) ────────────────
    link_y = center_y + int(size * 0.06)
    link_left = left_x + monitor_w
    link_right = right_x
    if link_right > link_left:
        # Animated-style dashed line effect (3 dots)
        dot_r = max(1, int(size * 0.012))
        num_dots = 3
        for i in range(num_dots):
            x = link_left + (link_right - link_left) * i // (num_dots - 1)
            draw.ellipse(
                [x - dot_r, link_y - dot_r, x + dot_r, link_y + dot_r],
                fill=COLOR_ACCENT,
            )

    # ── Small "power" dot indicator (top-right of right monitor) ─────────
    dot_r = max(2, int(size * 0.022))
    dot_x = right_x + monitor_w + int(size * 0.01)
    dot_y = right_y - int(size * 0.02)
    draw.ellipse(
        [dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r],
        fill=(34, 197, 94),  # green = running
    )
    # White border around dot
    draw.ellipse(
        [dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r],
        outline=COLOR_FG,
        width=max(1, int(size * 0.008)),
    )

    return img


def create_round_icon(size: int) -> Image.Image:
    """Create round icon variant (for ic_launcher_round)."""
    img = create_icon(size)
    # Create circular mask
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([0, 0, size - 1, size - 1], fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, mask=mask)
    return result


def main():
    for density, size in ICON_SIZES.items():
        # Create output dir
        mipmap_dir = os.path.join(OUTPUT_DIR, f"mipmap-{density}")
        os.makedirs(mipmap_dir, exist_ok=True)

        # Generate icon
        icon = create_icon(size)
        icon_path = os.path.join(mipmap_dir, "ic_launcher.png")
        icon.save(icon_path, "PNG")
        print(f"Saved: {icon_path} ({size}x{size})")

        # Generate round icon
        round_icon = create_round_icon(size)
        round_icon_path = os.path.join(mipmap_dir, "ic_launcher_round.png")
        round_icon.save(round_icon_path, "PNG")
        print(f"Saved: {round_icon_path} ({size}x{size})")

    print("\n✅ All icons generated!")


if __name__ == "__main__":
    main()
