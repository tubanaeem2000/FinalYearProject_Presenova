"""
AI Presentation Generator Service (Professional Executive Edition)
Generates elite, McKinsey/Gamma-grade presentation outlines using Gemini 3.6 Flash (with local fallback)
and programmatically builds polished PowerPoint (.pptx) decks featuring:
- High-resolution curated editorial imagery embedded on key slides
- Programmatically synthesized Matplotlib data visualizations
- Multi-column card grids, stat callout spotlights, and sequential process timelines
- 16:9 widescreen layout with professional typography, contrast accents, and custom themes
"""

import os
import json
import logging
import uuid
import re
import tempfile
import hashlib
import requests
from typing import Dict, Any, List, Optional
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from PIL import Image, ImageDraw
try:
    from pptx.enum.text import MSO_ANCHOR
except ImportError:
    MSO_ANCHOR = None

logger = logging.getLogger(__name__)

# Folders
GENERATED_FOLDER = os.path.join(os.getcwd(), 'instance', 'generated_presentations')
IMAGE_CACHE_FOLDER = os.path.join(os.getcwd(), 'instance', 'image_cache')
os.makedirs(GENERATED_FOLDER, exist_ok=True)
os.makedirs(IMAGE_CACHE_FOLDER, exist_ok=True)

# Curated High-Resolution Topic Photography (Unsplash Direct CDN Links - Royalty Free)
CURATED_TOPIC_PHOTOS = {
    'ai': [
        'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1080&q=80',  # Abstract Neural Mesh
        'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=1080&q=80',  # AI Brain Digital
        'https://images.unsplash.com/photo-1677442136019-21780efad99a?w=1080&q=80',  # AI Robot Hand
    ],
    'healthcare': [
        'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=1080&q=80',  # Doctor with Tablet
        'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=1080&q=80',  # Medical Diagnostics
        'https://images.unsplash.com/photo-1532938911079-1b06ac7ceec7?w=1080&q=80',  # Hospital Clinical Lab
    ],
    'tech': [
        'https://images.unsplash.com/photo-1518770660439-4636190af475?w=1080&q=80',  # Hardware Circuit Chip
        'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=1080&q=80',  # Cyber Security Server
        'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1080&q=80',  # Global Cloud Network
    ],
    'business': [
        'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1080&q=80',  # Corporate Skyscraper Glass
        'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1080&q=80',  # Financial Analytics Dashboard
        'https://images.unsplash.com/photo-1552664730-d307ca884978?w=1080&q=80',  # Team Strategy Meeting
    ],
    'education': [
        'https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=1080&q=80',  # Library & Research
        'https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=1080&q=80',  # Students Collaborating
        'https://images.unsplash.com/photo-1509062522246-3755977927d7?w=1080&q=80',  # Academic Lecture
    ],
    'science': [
        'https://images.unsplash.com/photo-1507413245164-6160d8298b31?w=1080&q=80',  # Laboratory Science
        'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=1080&q=80',  # Chemical Research Test Tubes
        'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=1080&q=80',  # Space Orbit Satellite
    ],
    'default': [
        'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1080&q=80',
        'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1080&q=80',
        'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1080&q=80',
    ]
}

# Color Themes - Professional Agency Grade
THEMES = {
    'corporate_blue_geom': {
        'name': 'Corporate Geometric Blue',
        'has_geometric_accents': True,
        'bg_color': RGBColor(248, 250, 253),       # Crisp Ice White
        'card_color': RGBColor(255, 255, 255),     # White Card
        'card_border': RGBColor(218, 228, 240),    # Soft Slate Blue
        'title_color': RGBColor(11, 44, 77),       # Deep Executive Navy
        'text_color': RGBColor(30, 41, 59),        # Slate 800
        'subtext_color': RGBColor(100, 116, 139),  # Slate 500
        'accent_color': RGBColor(0, 150, 199),     # Bright Cyan/Teal
        'highlight_bg': RGBColor(224, 242, 254),   # Soft Sky
        'badge_bg': RGBColor(3, 105, 161),         # Navy Teal
        'primary_accent': RGBColor(2, 62, 125),    # Dark Sapphire
        'chart_palette': ['#0077b6', '#0096c7', '#023e8a', '#48cae4', '#03045e', '#00b4d8']
    },
    'modern_infographic_yellow': {
        'name': 'Yellow & Slate Infographic',
        'has_yellow_top_bar': True,
        'bg_color': RGBColor(248, 250, 252),
        'card_color': RGBColor(255, 255, 255),
        'card_border': RGBColor(226, 232, 240),
        'title_color': RGBColor(15, 23, 42),       # Dark Slate
        'text_color': RGBColor(30, 41, 59),
        'subtext_color': RGBColor(100, 116, 139),
        'accent_color': RGBColor(234, 179, 8),     # Vibrant Yellow
        'highlight_bg': RGBColor(254, 249, 195),   # Yellow tint
        'badge_bg': RGBColor(217, 119, 6),         # Amber
        'primary_accent': RGBColor(234, 179, 8),
        'chart_palette': ['#eab308', '#ca8a04', '#0f172a', '#334155', '#64748b', '#f59e0b']
    },
    'creative_editorial': {
        'name': 'Creative Editorial Magazine',
        'is_editorial': True,
        'bg_color': RGBColor(253, 251, 247),       # Editorial Warm White
        'card_color': RGBColor(255, 255, 255),
        'card_border': RGBColor(231, 229, 228),
        'title_color': RGBColor(28, 25, 23),       # Warm Charcoal
        'text_color': RGBColor(41, 37, 36),
        'subtext_color': RGBColor(120, 113, 108),
        'accent_color': RGBColor(234, 88, 12),     # Terracotta Orange
        'highlight_bg': RGBColor(254, 242, 242),
        'badge_bg': RGBColor(194, 65, 12),
        'primary_accent': RGBColor(234, 88, 12),
        'chart_palette': ['#ea580c', '#292524', '#78716c', '#f97316', '#a8a29e', '#c2410c']
    },
    'modern_dark': {
        'name': 'Modern Dark',
        'bg_color': RGBColor(11, 15, 25),          # Deep Obsidian
        'card_color': RGBColor(24, 32, 47),        # Card Slate
        'card_border': RGBColor(51, 65, 85),       # Slate 700
        'title_color': RGBColor(56, 189, 248),      # Cyan 400
        'text_color': RGBColor(248, 250, 252),      # White
        'subtext_color': RGBColor(148, 163, 184),   # Slate 400
        'accent_color': RGBColor(129, 140, 248),    # Indigo 400
        'highlight_bg': RGBColor(30, 58, 138),     # Blue 900
        'badge_bg': RGBColor(14, 116, 144),        # Cyan 700
        'primary_accent': RGBColor(56, 189, 248),
        'chart_palette': ['#38bdf8', '#818cf8', '#34d399', '#f59e0b', '#f43f5e', '#a78bfa']
    },
    'corporate_clean': {
        'name': 'Corporate Clean',
        'bg_color': RGBColor(248, 250, 252),      # Pure Light
        'card_color': RGBColor(255, 255, 255),      # White
        'card_border': RGBColor(226, 232, 240),     # Border Gray
        'title_color': RGBColor(2, 132, 199),       # Sky 600
        'text_color': RGBColor(15, 23, 42),         # Dark Slate
        'subtext_color': RGBColor(71, 85, 105),     # Slate 600
        'accent_color': RGBColor(13, 148, 136),     # Teal 600
        'highlight_bg': RGBColor(224, 242, 254),    # Soft Sky
        'badge_bg': RGBColor(15, 118, 110),        # Teal 700
        'primary_accent': RGBColor(2, 132, 199),
        'chart_palette': ['#0284c7', '#0d9488', '#2563eb', '#d97706', '#dc2626', '#7c3aed']
    },
    'creative_neon': {
        'name': 'Creative Neon',
        'bg_color': RGBColor(18, 18, 24),          # Deep Charcoal
        'card_color': RGBColor(30, 30, 42),        # Dark Purple-Gray
        'card_border': RGBColor(63, 63, 85),
        'title_color': RGBColor(244, 63, 94),       # Rose 500
        'text_color': RGBColor(250, 250, 250),
        'subtext_color': RGBColor(161, 161, 170),
        'accent_color': RGBColor(245, 158, 11),    # Amber 500
        'highlight_bg': RGBColor(136, 19, 55),     # Rose 900
        'badge_bg': RGBColor(190, 18, 60),
        'primary_accent': RGBColor(244, 63, 94),
        'chart_palette': ['#f43f5e', '#f59e0b', '#06b6d4', '#10b981', '#a855f7', '#ec4899']
    },
    'academic_elegant': {
        'name': 'Academic Gold',
        'bg_color': RGBColor(15, 23, 42),          # Navy Blue
        'card_color': RGBColor(30, 41, 59),
        'card_border': RGBColor(71, 85, 105),
        'title_color': RGBColor(245, 158, 11),      # Gold Amber
        'text_color': RGBColor(226, 232, 240),
        'subtext_color': RGBColor(148, 163, 184),
        'accent_color': RGBColor(16, 185, 129),    # Emerald 500
        'highlight_bg': RGBColor(120, 53, 15),
        'badge_bg': RGBColor(180, 83, 9),
        'primary_accent': RGBColor(245, 158, 11),
        'chart_palette': ['#f59e0b', '#10b981', '#38bdf8', '#ef4444', '#8b5cf6', '#d97706']
    }
}


def _get_topic_category(topic_text: str) -> str:
    """Infer the broad category of the topic for curated photography selection."""
    t = topic_text.lower()
    if any(k in t for k in ['health', 'medic', 'doctor', 'hospital', 'patient', 'clinic', 'pharma', 'disease', 'surgery']):
        return 'healthcare'
    if any(k in t for k in ['ai', 'artificial intelligence', 'machine learning', 'deep learning', 'neural', 'robot', 'llm', 'gpt']):
        return 'ai'
    if any(k in t for k in ['cloud', 'software', 'cyber', 'code', 'data', 'algorithm', 'system', 'network', 'quantum', 'iot', 'hardware']):
        return 'tech'
    if any(k in t for k in ['business', 'finance', 'startup', 'market', 'strategy', 'revenue', 'invest', 'sales', 'growth', 'bank']):
        return 'business'
    if any(k in t for k in ['science', 'physics', 'chem', 'bio', 'space', 'astronomy', 'energy', 'solar', 'climate']):
        return 'science'
    if any(k in t for k in ['education', 'study', 'learn', 'student', 'school', 'university', 'teach', 'thesis', 'defense']):
        return 'education'
    return 'default'


def fetch_or_create_slide_image(topic: str, slide_num: int, theme: Dict[str, Any]) -> str:
    """
    Retrieves or generates a high-resolution professional image for the slide.
    1. Attempts to download from curated high-res photography CDN.
    2. Fallback: Generates a sleek geometric card with PIL locally.
    """
    category = _get_topic_category(topic)
    photo_list = CURATED_TOPIC_PHOTOS.get(category, CURATED_TOPIC_PHOTOS['default'])
    photo_url = photo_list[(slide_num - 1) % len(photo_list)]

    url_hash = hashlib.md5(photo_url.encode('utf-8')).hexdigest()[:12]
    cached_path = os.path.join(IMAGE_CACHE_FOLDER, f"img_{category}_{url_hash}.jpg")

    # If already cached, reuse
    if os.path.exists(cached_path) and os.path.getsize(cached_path) > 5000:
        return cached_path

    # Try downloading high-res curated photography
    try:
        resp = requests.get(photo_url, timeout=5, headers={'User-Agent': 'Presenova-Presentation-Engine/1.0'})
        if resp.status_code == 200 and len(resp.content) > 5000:
            with open(cached_path, 'wb') as f:
                f.write(resp.content)
            logger.info(f"[presentation_generator] Cached high-res photo for {category} at {cached_path}")
            return cached_path
    except Exception as e:
        logger.warning(f"[presentation_generator] Could not fetch photo from CDN: {e}. Generating local visual graphic.")

    # Fallback: Generate a branded, professional cover graphic with PIL
    fallback_path = os.path.join(IMAGE_CACHE_FOLDER, f"fallback_{category}_{slide_num}.png")
    try:
        W, H = 1080, 810
        img = Image.new('RGB', (W, H), color=(11, 15, 25))
        draw = ImageDraw.Draw(img)

        # Dark gradient background
        for y in range(H):
            r = int(11 + (y / H) * 18)
            g = int(15 + (y / H) * 30)
            b = int(25 + (y / H) * 55)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # Diagonal stripe accents (top-right)
        for i in range(0, 600, 28):
            draw.line([(W - 20 + i, 0), (W + i, 200)], fill=(56, 189, 248, 40), width=2)

        # Bold accent block — bottom 28%
        brand_top = int(H * 0.72)
        for y in range(brand_top, H):
            alpha = int(180 + (y - brand_top) / (H - brand_top) * 75)
            r = max(0, min(255, 2 - int((y - brand_top) * 0.02)))
            g = max(0, min(255, 132 - int((y - brand_top) * 0.3)))
            b = max(0, min(255, 199 - int((y - brand_top) * 0.5)))
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # Thin accent top-bar
        draw.rectangle([0, 0, W, 8], fill=(56, 189, 248))

        # Large circle watermark (top-right)
        draw.ellipse([W - 320, -120, W + 80, 280], outline=(56, 189, 248), width=3)
        draw.ellipse([W - 260, -60, W + 20, 220], outline=(129, 140, 248), width=1)

        # PRESENOVA AI watermark text
        draw.text((36, 20), "PRESENOVA AI", fill=(255, 255, 255, 180))
        # Topic category label
        draw.text((36, brand_top + 18), category.upper().replace('_', ' '), fill=(255, 255, 255, 220))

        img.save(fallback_path, quality=92)
        return fallback_path
    except Exception:
        return ""


def generate_slide_visual_chart(chart_info: Dict[str, Any], theme: Dict[str, Any], output_path: str) -> str:
    """
    Programmatically generate a theme-matched visual chart using matplotlib and save as PNG.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    chart_type = chart_info.get('chart_type', 'bar').lower()
    title = chart_info.get('title', 'Empirical Metrics & Performance')
    labels = chart_info.get('labels', ['Baseline', 'Optimized', 'Target', 'Peak'])
    values = chart_info.get('values', [42, 68, 85, 94])

    def _to_hex(rgb):
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    bg_hex = _to_hex(theme['card_color'])
    title_hex = _to_hex(theme['title_color'])
    accent_hex = _to_hex(theme['accent_color'])
    text_hex = _to_hex(theme['text_color'])
    subtext_hex = _to_hex(theme['subtext_color'])
    palette = theme.get('chart_palette', ['#38bdf8', '#818cf8', '#34d399', '#f59e0b', '#f43f5e'])

    fig, ax = plt.subplots(figsize=(6.2, 4.3), dpi=160)
    fig.patch.set_facecolor(bg_hex)
    ax.set_facecolor(bg_hex)

    if chart_type == 'donut':
        wedges, texts, autotexts = ax.pie(
            values[:len(labels)],
            labels=labels,
            autopct='%1.0f%%',
            startangle=140,
            colors=palette[:len(labels)],
            wedgeprops=dict(width=0.45, edgecolor=bg_hex, linewidth=2),
            textprops=dict(color=text_hex, fontsize=9.5, fontweight='bold')
        )
        for at in autotexts:
            at.set_color('#ffffff')
            at.set_fontsize(9.5)
            at.set_fontweight('bold')
        ax.set_title(title, color=title_hex, fontsize=11, fontweight='bold', pad=12)

    elif chart_type == 'line':
        ax.plot(labels, values, color=title_hex, marker='o', linewidth=3.5, markersize=9, markerfacecolor=accent_hex)
        ax.fill_between(range(len(labels)), values, color=title_hex, alpha=0.18)
        for i, val in enumerate(values):
            ax.annotate(f"{val}%" if isinstance(val, (int, float)) and val <= 100 else f"{val}",
                        (labels[i], values[i]), textcoords="offset points", xytext=(0, 8),
                        ha='center', color=text_hex, fontsize=9.5, fontweight='bold')
        ax.set_title(title, color=title_hex, fontsize=11, fontweight='bold', pad=12)
        ax.tick_params(colors=subtext_hex, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color('#475569')
        ax.grid(True, linestyle='--', alpha=0.25, color='#64748b')

    else:  # Default Bar Chart
        bars = ax.bar(labels, values, color=palette[:len(labels)], width=0.52, edgecolor=title_hex, linewidth=1.2)
        for bar in bars:
            height = bar.get_height()
            label_val = f"{height}%" if isinstance(height, (int, float)) and height <= 100 else f"{height}"
            ax.annotate(label_val,
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 4),
                        textcoords="offset points",
                        ha='center', va='bottom',
                        color=text_hex, fontsize=9.5, fontweight='bold')
        ax.set_title(title, color=title_hex, fontsize=11, fontweight='bold', pad=12)
        ax.tick_params(colors=subtext_hex, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color('#475569')
        ax.grid(axis='y', linestyle='--', alpha=0.25, color='#64748b')

    plt.tight_layout()
    fig.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    return output_path


def generate_circular_dials_graphic(dials_data: List[Dict[str, Any]], theme: Dict[str, Any], output_path: str) -> str:
    """
    Renders 3 or 4 circular percentage progress gauges side-by-side using Matplotlib.
    Matches Image 2 & 3 infographics (e.g. 35%, 75%, 45%, 55%).
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    def _to_hex(rgb):
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    bg_hex = _to_hex(theme['card_color'])
    text_hex = _to_hex(theme['text_color'])
    palette = theme.get('chart_palette', ['#0096c7', '#0284c7', '#38bdf8', '#818cf8'])

    n = min(4, max(2, len(dials_data)))
    fig, axes = plt.subplots(1, n, figsize=(2.8 * n, 2.8), dpi=160)
    fig.patch.set_facecolor(bg_hex)
    if n == 1:
        axes = [axes]

    for idx in range(n):
        ax = axes[idx]
        ax.set_facecolor(bg_hex)
        d = dials_data[idx]
        raw_pct = str(d.get('percent', d.get('number', '75'))).replace('%', '').strip()
        try:
            pct = float(raw_pct)
        except ValueError:
            pct = 75.0
        pct = max(0.0, min(100.0, pct))
        label = d.get('label', f'Metric {idx+1}')
        color = palette[idx % len(palette)]

        # Background track
        track_color = '#e2e8f0' if ('#fff' in bg_hex.lower() or '#f' in bg_hex.lower()) else '#334155'
        ax.pie([100], radius=1.0, colors=[track_color],
               wedgeprops=dict(width=0.22, edgecolor='none'))

        # Active progress arc
        remainder = 100.0 - pct
        ax.pie([pct, remainder], radius=1.0, colors=[color, 'none'], startangle=90, counterclock=False,
               wedgeprops=dict(width=0.22, edgecolor='none'))

        # Center percentage text
        ax.text(0, 0.06, f"{int(pct)}%", ha='center', va='center', fontsize=18, fontweight='bold', color=color)
        ax.text(0, -0.40, label[:18], ha='center', va='center', fontsize=8.5, fontweight='bold', color=text_hex)

    plt.tight_layout()
    fig.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    return output_path


def _draw_geometric_accents(slide, prs_width, prs_height, theme: Dict[str, Any], is_cover: bool = False):
    """
    Draws modern layered geometric corner chevrons and angular polygons
    inspired by Image 1 (Corporate Business Plan) and Image 2 (Yellow Infographic).
    """
    if theme.get('has_yellow_top_bar'):
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs_width, Inches(0.12))
        bar.fill.solid()
        bar.fill.fore_color.rgb = theme['accent_color']
        bar.line.fill.background()

    if theme.get('has_geometric_accents'):
        # Top-Right geometric layered right triangles
        tri1 = slide.shapes.add_shape(
            MSO_SHAPE.RIGHT_TRIANGLE,
            prs_width - Inches(3.2), Inches(0), Inches(3.2), Inches(2.2)
        )
        tri1.fill.solid()
        tri1.fill.fore_color.rgb = theme.get('primary_accent', theme['title_color'])
        tri1.line.fill.background()

        tri2 = slide.shapes.add_shape(
            MSO_SHAPE.RIGHT_TRIANGLE,
            prs_width - Inches(2.2), Inches(0), Inches(2.2), Inches(1.5)
        )
        tri2.fill.solid()
        tri2.fill.fore_color.rgb = theme['accent_color']
        tri2.line.fill.background()

        if is_cover:
            # Bottom-Left corner triangular accent
            tri3 = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_TRIANGLE,
                Inches(0), prs_height - Inches(2.4), Inches(3.4), Inches(2.4)
            )
            tri3.fill.solid()
            tri3.fill.fore_color.rgb = theme['accent_color']
            tri3.line.fill.background()
            tri3.rotation = 180


def classify_slide_intent(title: str, bullets: List[str], cards: List[Any], requested_type: Optional[str] = None) -> str:
    """
    Deterministically classifies slide content into optimal layout archetype:
    'title' | 'conclusion' | 'key_visual' | 'swot' | 'horizontal_pills' | 'circular_dials' |
    'process_chevrons' | 'team_personas' | 'editorial_split' | 'chart' | 'stat_callout' |
    'comparison_grid' | 'timeline' | 'visual_split'
    """
    if requested_type:
        req = requested_type.lower()
        if req in ('conclusion', 'thank_you', 'closing', 'thankyou'):
            return 'conclusion'
        if req in ('key_visual', 'section_divider', 'divider', 'section'):
            return 'key_visual'
        if req in ('swot', 'swot_analysis'):
            return 'swot'
        if req in ('horizontal_pills', 'objectives', 'pills', 'pills_abc'):
            return 'horizontal_pills'
        if req in ('circular_dials', 'dials', 'circular_metrics', 'gauges'):
            return 'circular_dials'
        if req in ('process_chevrons', 'chevrons', 'process_steps'):
            return 'process_chevrons'
        if req in ('team_personas', 'team', 'personas', 'bios'):
            return 'team_personas'
        if req in ('editorial_split', 'magazine', 'editorial'):
            return 'editorial_split'
        if req in ('chart', 'metrics', 'financial'):
            return 'chart'
        if req in ('stat', 'stat_callout', 'stats'):
            return 'stat_callout'
        if req in ('timeline', 'roadmap', 'process'):
            return 'timeline'
        if req in ('comparison', 'comparison_grid', 'cards'):
            return 'comparison_grid'
        if req in ('visual_split', 'visual'):
            return 'visual_split'
        if req in ('split', 'focus'):
            return 'split'
        if req == 'title':
            return 'title'

    full_text = (title + " " + " ".join(bullets) + " " + " ".join([str(c) for c in cards])).lower()

    if any(k in title.lower() for k in ['thank you', 'conclusion', 'closing', 'next steps', 'key takeaways']):
        return 'conclusion'
    if any(k in full_text for k in ['swot', 'strengths', 'weaknesses', 'threats']):
        return 'swot'
    if any(k in full_text for k in ['objective', 'overview &', 'deliverable', 'agenda', 'scope']):
        return 'horizontal_pills'
    if any(k in full_text for k in ['team', 'leadership', 'founders', 'advisors', 'personnel', 'squad']):
        return 'team_personas'
    if any(k in full_text for k in ['step 1', 'stage 1', 'workflow', 'chevrons']):
        return 'process_chevrons'
    if any(k in full_text for k in ['progress dial', 'percentage dial', 'gauge', 'dials']):
        return 'circular_dials'
    if any(k in full_text for k in ['growth', 'trend', 'distribution', 'revenue', 'performance', 'latency', 'benchmark', 'accuracy rate', 'financial', 'metrics']):
        return 'chart' if ('%' in full_text or 'rate' in full_text or 'vs' in full_text) else 'stat_callout'
    if any(k in full_text for k in ['phase 1', 'phase 2', 'roadmap', 'timeline', 'milestones']):
        return 'timeline'
    if any(k in full_text for k in [' vs ', 'versus', 'compared to', 'pros and cons', 'advantages and', 'pillars']):
        return 'comparison_grid'
    if any(k in full_text for k in ['efficiency', 'retention', 'kpi', 'sla', 'uptime', 'accuracy']):
        return 'stat_callout'
    if any(k in full_text for k in ['story', 'editorial', 'magazine', 'spotlight']):
        return 'editorial_split'

    return 'visual_split'


def _generate_with_gemini(topic: str, slide_count: int, tone: str, audience: str, seed_text: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Attempt generation via Gemini 2.5 Flash for rich, domain-specific slides."""
    try:
        from services.ai.gemini_provider import GeminiProvider
        provider = GeminiProvider(timeout_seconds=45.0, max_retries=2)
        if not provider.is_available():
            return None

        # Build the available slide types pool for rotation across full slide_count
        _type_pool = [
            ("horizontal_pills", "Strategic Objectives & Vision", '{"cards": [{"title": "Objective Alpha: ...", "description": "..."}, {"title": "Objective Beta: ...", "description": "..."}, {"title": "Objective Gamma: ...", "description": "..."}], "bullets": []}'),
            ("swot", "Comprehensive SWOT Matrix", '{"swot_data": {"strengths": ["...", "..."], "weaknesses": ["...", "..."], "opportunities": ["...", "..."], "threats": ["...", "..."]}, "bullets": []}'),
            ("chart", "Empirical Benchmark Metrics", '{"chart_data": {"chart_type": "bar", "title": "Performance Index", "labels": ["Efficiency", "Accuracy", "Throughput", "Uptime"], "values": [78, 92, 85, 99]}, "bullets": ["...", "..."]}'),
            ("circular_dials", "Performance Gauges & Operational Rates", '{"dials": [{"percent": 88, "label": "Retention Rate"}, {"percent": 64, "label": "Coverage"}, {"percent": 95, "label": "Accuracy SLA"}], "bullets": ["...", "..."]}'),
            ("process_chevrons", "Phased Execution Workflow", '{"cards": [{"title": "Step 1: Discovery", "description": "..."}, {"title": "Step 2: Build", "description": "..."}, {"title": "Step 3: Validate", "description": "..."}, {"title": "Step 4: Scale", "description": "..."}], "bullets": []}'),
            ("team_personas", "Leadership & Squad Alignment", '{"cards": [{"title": "Name A", "role": "CTO", "description": "..."}, {"title": "Name B", "role": "CPO", "description": "..."}, {"title": "Name C", "role": "Lead Engineer", "description": "..."}], "bullets": []}'),
            ("stat_callout", "High-Impact KPI Spotlight", '{"stat_metrics": [{"number": "94%", "badge": "▲ Precision", "label": "Model Accuracy"}, {"number": "3.8x", "badge": "⚡ Speed", "label": "Throughput Factor"}, {"number": "100%", "badge": "✓ Uptime", "label": "System Reliability"}], "bullets": []}'),
            ("timeline", "Implementation Roadmap", '{"cards": [{"title": "Phase 1: Readiness", "description": "..."}, {"title": "Phase 2: Rollout", "description": "..."}, {"title": "Phase 3: Optimize", "description": "..."}], "bullets": []}'),
            ("editorial_split", "Strategic Narrative & Spotlight", '{"bullets": ["...", "...", "..."]}'),
        ]

        # Build dynamic slide template list (slides 2 through N-1)
        dynamic_slides_json = []
        dynamic_slides_json.append("""
    {{
      "slide_number": 1,
      "title": "...",
      "subtitle": "...",
      "type": "title",
      "suggested_layout": "title",
      "bullets": [],
      "speaker_notes": "..."
    }}""")

        inner_count = max(1, slide_count - 2)  # exclude title + conclusion
        for i in range(inner_count):
            pool_entry = _type_pool[i % len(_type_pool)]
            stype, default_title, extra_json = pool_entry
            snum = i + 2
            dynamic_slides_json.append(f"""
    {{
      "slide_number": {snum},
      "title": "{default_title}",
      "key_takeaway": "...",
      "type": "{stype}",
      "suggested_layout": "{stype}",
      {extra_json.strip('{}')},
      "speaker_notes": "..."
    }}""")

        # Last slide: Conclusion
        conclusion_num = slide_count
        dynamic_slides_json.append(f"""
    {{
      "slide_number": {conclusion_num},
      "title": "Key Takeaways & Next Steps",
      "subtitle": "Thank you for your attention.",
      "type": "conclusion",
      "suggested_layout": "conclusion",
      "bullets": ["...", "...", "..."],
      "contact_info": "Contact: team@organization.com",
      "speaker_notes": "Close with energy. Invite questions and highlight the single most important action item."
    }}""")

        slides_template = ",\n".join(dynamic_slides_json)

        seed_context_block = ""
        if seed_text:
            seed_context_block = f"""\n\nREFERENCE DOCUMENT CONTEXT (derive topic-specific content, real metrics, and domain terminology from this):\n---\n{seed_text[:2000]}\n---"""

        prompt = f"""You are an elite executive presentation strategist at McKinsey, BCG, and Gamma.ai.
Generate an EXTRAORDINARY, highly specific, professional presentation outline on the topic: "{topic}".

AUDIENCE: {audience}
TONE: {tone}
REQUIRED SLIDE COUNT: exactly {slide_count} slides{seed_context_block}

STRICT CRITERIA:
- Do NOT output generic, vague text. Use real, deep, concrete domain terminology, real-world metrics, and proven strategic frameworks.
- Slide 1 MUST be type "title" with a compelling, punchy subtitle.
- Slide {slide_count} (the LAST slide) MUST be type "conclusion" — include 3 key takeaways and a next-steps CTA.
- For slides 2 through {slide_count - 1}, use the most appropriate type from: horizontal_pills, swot, chart, circular_dials, process_chevrons, team_personas, stat_callout, timeline, editorial_split, key_visual.
- Every non-title/non-conclusion slide MUST include a 1-line "key_takeaway" and 1 actionable "speaker_notes".
- chart_data MUST have real, plausible numeric values. Dials MUST have realistic percentages.
- Do NOT repeat the same slide type twice unless the deck has more than 9 slides.

Return ONLY raw valid JSON (no markdown, no backticks):
{{
  "presentation_title": "...",
  "subtitle": "...",
  "topic": "{topic}",
  "target_audience": "{audience}",
  "tone": "{tone}",
  "slides": [{slides_template}]
}}"""

        data = provider.generate_structured(prompt=prompt)
        if not data or not isinstance(data, dict):
            raw_text = provider.generate(prompt=prompt)
            if raw_text:
                clean_text = re.sub(r'^```json\s*', '', raw_text.strip(), flags=re.MULTILINE)
                clean_text = re.sub(r'^```\s*', '', clean_text, flags=re.MULTILINE)
                data = json.loads(clean_text)

        if data and isinstance(data, dict) and 'slides' in data and len(data['slides']) >= 3:
            logger.info(f"[presentation_generator] Successfully synthesized rich outline via Gemini: {len(data['slides'])} slides")
            data['outline_id'] = f"out_{uuid.uuid4().hex[:10]}"
            # Ensure suggested_layout is synced
            for s in data['slides']:
                if 'suggested_layout' not in s:
                    s['suggested_layout'] = s.get('type', 'split')
            return data

    except Exception as e:
        logger.warning(f"[presentation_generator] Gemini synthesis failed ({e}). Falling back to enriched local engine.")
        return None


def generate_presentation_outline(
    topic: str,
    slide_count: int = 5,
    tone: str = "Professional",
    audience: str = "General Audience",
    seed_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a structured, multi-archetype presentation outline.
    Prefers Gemini 3.6 Flash for deep domain content; falls back to enriched local generator.
    """
    slide_count = max(3, min(20, int(slide_count)))

    # 1. Try Gemini 3.6 Flash if no offline force flag
    offline = os.getenv('FORCE_OFFLINE_MODE', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    if not offline:
        ai_outline = _generate_with_gemini(topic, slide_count, tone, audience, seed_text=seed_text)
        if ai_outline:
            return ai_outline

    # 2. Local Enriched Domain Outline Generator
    topic_clean = topic.strip().title() if topic.strip() else "Strategic Presentation"
    category = _get_topic_category(topic)

    # Tailored domain bullets based on topic category
    domain_bullets = {
        'healthcare': [
            f"Clinical diagnostics accuracy scaling through automated inference models.",
            f"Regulatory compliance, HIPAA governance, and patient privacy protocols.",
            f"Reducing triage latency by 45% across acute inpatient admissions."
        ],
        'ai': [
            f"Scalable neural model training pipelines with low-precision quantization.",
            f"Mitigating inference hallucinations via structured verification passes.",
            f"Sub-20ms latency SLA across distributed multi-region edge nodes."
        ],
        'business': [
            f"Capturing high-margin market share through differentiated value propositions.",
            f"Optimizing operating cash flow and accelerating sales pipeline conversion.",
            f"Institutionalizing agile execution rhythms across cross-functional squads."
        ],
        'default': [
            f"Establishing clear operational benchmarks and baseline standards.",
            f"Eliminating systemic bottlenecks through automated workflow integration.",
            f"Delivering measurable return on investment across core milestone goals."
        ]
    }
    sample_bullets = domain_bullets.get(category, domain_bullets['default'])

    slides: List[Dict[str, Any]] = [
        {
            "slide_number": 1,
            "title": f"Mastering {topic_clean}",
            "subtitle": f"An Executive {tone} Blueprint for {audience}",
            "type": "title",
            "suggested_layout": "title",
            "bullets": [],
            "speaker_notes": f"Welcome everyone. Today we examine strategic frameworks and practical execution for {topic_clean}."
        },
        {
            "slide_number": 2,
            "title": "Strategic Overview & Core Objectives",
            "key_takeaway": "Three synchronized executive priorities driving mission success",
            "type": "horizontal_pills",
            "suggested_layout": "horizontal_pills",
            "cards": [
                { "title": "Objective A: Baseline Normalization & Standards", "description": f"Enforce robust data integrity, compliance governance, and quality metrics across {topic_clean}." },
                { "title": "Objective B: High-Throughput Processing Scale", "description": "Streamline operational workflows to eliminate handoff friction and accelerate delivery." },
                { "title": "Objective C: Automated Verification & Governance", "description": "Deploy real-time telemetry scorecards with automated validation gates at enterprise scale." }
            ],
            "bullets": [],
            "speaker_notes": "Walk through the 3 primary strategic pillars with clear execution focus."
        },
        {
            "slide_number": 3,
            "title": "Comprehensive SWOT Analysis Matrix",
            "key_takeaway": "Evaluating internal capabilities against external market forces",
            "type": "swot",
            "suggested_layout": "swot",
            "swot_data": {
                "strengths": [
                    f"Proprietary domain architecture tailored for {topic_clean}.",
                    "High operational velocity with deterministic latency SLAs."
                ],
                "weaknesses": [
                    "Integration overhead across legacy heterogeneous infrastructure.",
                    "Specialized talent requirements for advanced tuning passes."
                ],
                "opportunities": [
                    "Accelerating multi-region cloud adoption across target demographics.",
                    "Unlocking high-margin revenue through automated self-service."
                ],
                "threats": [
                    "Aggressive market entrants expanding open-source alternatives.",
                    "Evolving regulatory compliance and data localization standards."
                ]
            },
            "bullets": [],
            "speaker_notes": "Present strategic SWOT matrix to align executive stakeholders on risks and opportunities."
        },
        {
            "slide_number": 4,
            "title": "Empirical Performance & Benchmark Gains",
            "key_takeaway": "Quantifiable efficiency improvements across standard test baselines",
            "type": "chart",
            "suggested_layout": "chart",
            "chart_data": {
                "chart_type": "bar",
                "title": f"{topic_clean} Performance Index (%)",
                "labels": ["Processing Speed", "Accuracy Rate", "Cost Efficiency", "System Uptime"],
                "values": [78, 92, 85, 99]
            },
            "bullets": [
                "Observed 78% speedup following pipeline parallelization.",
                "Overall evaluation reliability reached 92% across production runs.",
                "Maintained 99.9% uptime availability throughout peak stress loads."
            ],
            "speaker_notes": "Present empirical metrics to validate operational effectiveness."
        },
        {
            "slide_number": 5,
            "title": "Performance Gauges & Operational Rates",
            "key_takeaway": "Primary telemetry dials validating system health and engagement",
            "type": "circular_dials",
            "suggested_layout": "circular_dials",
            "dials": [
                { "percent": 88, "label": "Retention Rate" },
                { "percent": 65, "label": "Market Coverage" },
                { "percent": 94, "label": "Model Precision" }
            ],
            "bullets": [
                "User retention remains within top decile across comparable industry cohorts.",
                "Market penetration pacing 14% ahead of conservative projections.",
                "Model precision safeguards against false positives in critical decision paths."
            ],
            "speaker_notes": "Walk through the circular progress dials reflecting current operational trajectory."
        }
    ]

    # Additional slides if requested > 5
    if slide_count > 5:
        templates = [
            {
                "title": "Phased Execution & Operations Workflow",
                "key_takeaway": "Sequential 4-step delivery pipeline across deployment horizons",
                "type": "process_chevrons",
                "suggested_layout": "process_chevrons",
                "cards": [
                    { "title": "Discovery & Ingestion", "description": "Telemetry audit, baseline benchmarks, and schema synchronization." },
                    { "title": "Core Pipeline Execution", "description": "High-throughput transformations, model inferences, and edge validation." },
                    { "title": "Automated Quality Gates", "description": "Compliance checks, anomaly alerts, and regression safety passes." },
                    { "title": "Scale & Governance", "description": "Global rollout, executive dashboards, and ongoing feedback loops." }
                ],
                "bullets": [],
                "speaker_notes": "Review the 4-phase chevron workflow guiding operational execution."
            },
            {
                "title": "Leadership Team & Squad Alignment",
                "key_takeaway": "Cross-functional ownership driving strategic initiatives",
                "type": "team_personas",
                "suggested_layout": "team_personas",
                "cards": [
                    { "title": "Dr. Sarah Jenkins", "role": "Chief Technology Officer", "description": "15+ years architecting enterprise distributed systems and AI platforms." },
                    { "title": "Marcus Vance", "role": "Head of Product Strategy", "description": "Former McKinsey director specializing in operational scaling and growth." },
                    { "title": "Elena Rostova", "role": "Lead Systems Engineer", "description": "Expert in deterministic low-latency pipelines and compliance telemetry." }
                ],
                "bullets": [],
                "speaker_notes": "Introduce the leadership squad responsible for steering core deliverables."
            },
            {
                "title": "Strategic Narrative & Industry Spotlight",
                "key_takeaway": "Contextualizing transformative impact across the broader ecosystem",
                "type": "editorial_split",
                "suggested_layout": "editorial_split",
                "bullets": [
                    f"Structural divergence separating market leaders from legacy incumbents.",
                    f"Embedding continuous intelligence directly into primary {topic_clean} touchpoints.",
                    "Unlocking sustainable competitive advantage through disciplined execution."
                ],
                "speaker_notes": "Highlight the overarching narrative and strategic vision."
            },
            {
                "title": "High-Impact Performance Metrics",
                "key_takeaway": "Primary key performance indicators validating deployment success",
                "type": "stat_callout",
                "suggested_layout": "stat_callout",
                "stat_metrics": [
                    { "number": "94.6%", "badge": "▲ Precision", "label": "Model Validation Reliability" },
                    { "number": "3.8x", "badge": "⚡ Velocity", "label": "Throughput Acceleration Factor" },
                    { "number": "100%", "badge": "🔒 Private", "label": "Local-First Architecture Compliance" }
                ],
                "bullets": [],
                "speaker_notes": "Highlight the 3 primary KPI spotlights that demonstrate impact."
            },
            {
                "title": "Implementation Roadmap & Milestones",
                "key_takeaway": "Phased milestone execution timeline across strategic quarters",
                "type": "timeline",
                "suggested_layout": "timeline",
                "cards": [
                    { "title": "Phase 1: Readiness & Baseline", "description": "Technical audit, environment setup, and baseline telemetry capture." },
                    { "title": "Phase 2: Core Rollout", "description": "Pipeline deployment, continuous validation, and automated stress testing." },
                    { "title": "Phase 3: Scale & Institutionalize", "description": "Cross-platform release, user onboarding, and continuous optimization." }
                ],
                "bullets": [],
                "speaker_notes": "Walk through execution milestones and set realistic delivery horizons."
            }
        ]
        for extra in templates:
            if len(slides) < slide_count:
                slides.append(extra)

        while len(slides) < slide_count:
            idx = len(slides) + 1
            slides.append({
                "slide_number": idx,
                "title": f"Operational Deep Dive: Component #{idx - 5}",
                "key_takeaway": "Granular risk management, telemetry tracking, and contingency bounds",
                "type": "cards" if idx % 2 == 0 else "split",
                "suggested_layout": "comparison_grid" if idx % 2 == 0 else "split",
                "cards": [
                    { "title": "Capability A", "description": "Continuous automated validation against compliance standards." },
                    { "title": "Capability B", "description": "Low-overhead telemetry streaming without performance degradation." },
                    { "title": "Capability C", "description": "Scalable modularity allowing future component interchangeability." }
                ] if idx % 2 == 0 else [],
                "bullets": [
                    f"Rigorous operational audit of technical component #{idx - 5}.",
                    "Automated edge case handling and fallback resilience.",
                    "Measurable alignment with overall presentation objectives."
                ] if idx % 2 != 0 else [],
                "speaker_notes": f"Discuss technical guidelines and best practices for area #{idx - 5}."
            })

    # Ensure a professional Conclusion slide is always the last slide
    conclusion_slide = {
        "slide_number": slide_count,
        "title": "Key Takeaways & Next Steps",
        "subtitle": "Thank you for your attention.",
        "type": "conclusion",
        "suggested_layout": "conclusion",
        "bullets": [
            f"Strategic alignment around {topic_clean} drives measurable, enterprise-grade outcomes.",
            "Systematic execution of the defined pillars accelerates time-to-value by 40%.",
            "Next step: Schedule stakeholder review and initiate Pilot Phase within 30 days."
        ],
        "contact_info": "Questions? Reach out to the presenting team.",
        "speaker_notes": "Close with confidence. Reiterate the 3 takeaways and invite questions."
    }

    # Replace or append the conclusion slide
    final_slides = slides[:slide_count - 1]
    for i, s in enumerate(final_slides):
        s["slide_number"] = i + 1
    conclusion_slide["slide_number"] = slide_count
    final_slides.append(conclusion_slide)

    return {
        "outline_id": f"out_{uuid.uuid4().hex[:10]}",
        "presentation_title": f"Mastering {topic_clean}",
        "subtitle": f"An Executive {tone} Blueprint for {audience}",
        "topic": topic,
        "target_audience": audience,
        "tone": tone,
        "seven_cs_applied": ["Clarity", "Conciseness", "Completeness", "Concreteness", "Consideration", "Correctness", "Courtesy"],
        "slides": final_slides
    }


def build_pptx_from_outline(
    outline_data: Dict[str, Any],
    theme_name: str = 'modern_dark',
    custom_overrides: Optional[Dict[str, Any]] = None
) -> str:
    """
    Programmatically constructs an executive-grade, professional PowerPoint (.pptx) deck.
    Embeds high-resolution curated photography, Matplotlib data visualizations, and modern card structures.
    """
    theme = THEMES.get(theme_name, THEMES['modern_dark'])
    overrides = custom_overrides or {}
    show_slide_numbers = overrides.get('show_slide_numbers', True)
    confidentiality_tag = overrides.get('confidentiality_tag', 'Presenova Executive Presentation')

    prs = Presentation()
    prs.slide_width = Inches(13.333)  # 16:9 Widescreen ratio
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    topic = outline_data.get('topic', 'Presentation')
    slides = outline_data.get('slides', [])
    total_slides = len(slides)

    for slide_info in slides:
        slide = prs.slides.add_slide(blank_layout)

        # 1. Slide Solid Background
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = theme['bg_color']
        bg.line.fill.background()

        slide_num = slide_info.get('slide_number', 1)
        raw_type = slide_info.get('suggested_layout') or slide_info.get('type', 'visual_split')
        slide_type = classify_slide_intent(
            title=slide_info.get('title', ''),
            bullets=slide_info.get('bullets', []),
            cards=slide_info.get('cards', []),
            requested_type=raw_type
        )

        is_title_slide = (slide_num == 1 or slide_type == 'title')

        if is_title_slide:
            # Draw geometric corner accents / brand bars for styled themes (cover mode)
            _draw_geometric_accents(slide, prs.slide_width, prs.slide_height, theme, is_cover=True)

            # ── HERO COVER SLIDE WITH HIGH-RES SPLIT PHOTOGRAPHY ─────────────
            # Left Card Container for Title & Branding
            hero_card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(0.8), Inches(6.8), Inches(5.9)
            )
            hero_card.fill.solid()
            hero_card.fill.fore_color.rgb = theme['card_color']
            hero_card.line.color.rgb = theme['card_border']

            # Category Tag Pill
            pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.3), Inches(1.3), Inches(2.2), Inches(0.42))
            pill.fill.solid()
            pill.fill.fore_color.rgb = theme['badge_bg']
            pill.line.fill.background()
            pill_tf = pill.text_frame
            pill_p = pill_tf.paragraphs[0]
            pill_p.text = "EXECUTIVE BRIEFING"
            pill_p.font.size = Pt(11)
            pill_p.font.bold = True
            pill_p.font.color.rgb = RGBColor(255, 255, 255)
            pill_p.alignment = PP_ALIGN.CENTER

            # Title Textbox
            txBox = slide.shapes.add_textbox(Inches(1.3), Inches(2.0), Inches(5.8), Inches(4.3))
            tf = txBox.text_frame
            tf.word_wrap = True

            p = tf.paragraphs[0]
            p.text = slide_info.get('title', outline_data.get('presentation_title', 'Presentation Title'))
            p.font.size = Pt(36)
            p.font.bold = True
            p.font.color.rgb = theme['title_color']

            subtitle_text = slide_info.get('subtitle') or outline_data.get('subtitle', '')
            if subtitle_text:
                p2 = tf.add_paragraph()
                p2.text = subtitle_text
                p2.font.size = Pt(16)
                p2.font.color.rgb = theme['subtext_color']
                p2.space_before = Pt(14)

            # Audience & Tone info as separate styled shapes (no raw emoji in XML)
            meta_line = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Inches(1.3), Inches(4.75), Inches(5.4), Inches(0.04)
            )
            meta_line.fill.solid()
            meta_line.fill.fore_color.rgb = theme['accent_color']
            meta_line.line.fill.background()

            aud_box = slide.shapes.add_textbox(Inches(1.3), Inches(4.9), Inches(5.4), Inches(0.5))
            aud_tf = aud_box.text_frame
            aud_p = aud_tf.paragraphs[0]
            aud_p.text = f"Audience: {outline_data.get('target_audience', 'Executive Board')}   •   Tone: {outline_data.get('tone', 'Professional')}"
            aud_p.font.size = Pt(12)
            aud_p.font.bold = True
            aud_p.font.color.rgb = theme['accent_color']

            # Right Card: High-Resolution Topic Photography
            img_path = fetch_or_create_slide_image(topic, slide_num=1, theme=theme)
            if img_path and os.path.exists(img_path):
                try:
                    slide.shapes.add_picture(img_path, Inches(7.9), Inches(0.8), Inches(4.6), Inches(5.9))
                except Exception as ie:
                    logger.warning(f"Could not embed hero image: {ie}")

        else:
            # ── SLIDE HEADER BAR ─────────────────────────────────────────────
            header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.733), Inches(1.1))
            tf_head = header_box.text_frame
            tf_head.word_wrap = True

            p_title = tf_head.paragraphs[0]
            p_title.text = slide_info.get('title', f"Slide {slide_num}")
            p_title.font.size = Pt(26)
            p_title.font.bold = True
            p_title.font.color.rgb = theme['title_color']

            if slide_info.get('key_takeaway'):
                p_sub = tf_head.add_paragraph()
                p_sub.text = f"💡 {slide_info.get('key_takeaway')}"
                p_sub.font.size = Pt(13)
                p_sub.font.color.rgb = theme['accent_color']
                p_sub.space_before = Pt(3)

            # Draw geometric corner accents / brand bars for styled themes
            _draw_geometric_accents(slide, prs.slide_width, prs.slide_height, theme, is_cover=False)

            cards = slide_info.get('cards', [])
            bullets = slide_info.get('bullets', [])
            stat_metrics = slide_info.get('stat_metrics', [])

            # ── LAYOUT 1: SWOT ANALYSIS 4-PILLAR MATRIX ──────────────────────
            if slide_type == 'swot':
                swot_data = slide_info.get('swot_data', {})
                swot_cols = [
                    {
                        "letter": "S",
                        "title": "STRENGTHS",
                        "color": theme.get('primary_accent', theme['title_color']),
                        "items": swot_data.get('strengths', [
                            "Proprietary domain architecture & low-latency execution.",
                            "High operational accuracy with verifiable telemetry."
                        ])
                    },
                    {
                        "letter": "W",
                        "title": "WEAKNESSES",
                        "color": RGBColor(71, 85, 105),  # Slate 600
                        "items": swot_data.get('weaknesses', [
                            "Integration friction across legacy heterogeneous systems.",
                            "Steep initial learning curve for specialized workflows."
                        ])
                    },
                    {
                        "letter": "O",
                        "title": "OPPORTUNITIES",
                        "color": theme['accent_color'],
                        "items": swot_data.get('opportunities', [
                            "Accelerating market expansion into enterprise accounts.",
                            "Automating continuous optimization loops via self-service."
                        ])
                    },
                    {
                        "letter": "T",
                        "title": "THREATS",
                        "color": RGBColor(185, 28, 28) if '#fff' in str(theme['bg_color']) else RGBColor(225, 29, 72),  # Rose/Red
                        "items": swot_data.get('threats', [
                            "Fast-following competitors adopting commoditized models.",
                            "Shifting regulatory compliance and data locality mandates."
                        ])
                    }
                ]

                col_w = Inches(2.72)
                col_gap = Inches(0.28)
                c_left_margin = Inches(0.8)

                for ci, sc in enumerate(swot_cols):
                    c_x = c_left_margin + ci * (col_w + col_gap)

                    # Pillar card container
                    p_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE, c_x, Inches(1.7), col_w, Inches(4.8)
                    )
                    p_card.fill.solid()
                    p_card.fill.fore_color.rgb = theme['card_color']
                    p_card.line.color.rgb = theme['card_border']

                    # Header color block — use RECTANGLE (not rounded) to avoid bleed artifact
                    h_block = slide.shapes.add_shape(
                        MSO_SHAPE.RECTANGLE, c_x, Inches(1.7), col_w, Inches(1.0)
                    )
                    h_block.fill.solid()
                    h_block.fill.fore_color.rgb = sc['color']
                    h_block.line.fill.background()

                    h_tf = h_block.text_frame
                    h_tf.word_wrap = True
                    h_p1 = h_tf.paragraphs[0]
                    h_p1.text = sc['letter']
                    h_p1.font.size = Pt(24)
                    h_p1.font.bold = True
                    h_p1.font.color.rgb = RGBColor(255, 255, 255)
                    h_p1.alignment = PP_ALIGN.CENTER

                    h_p2 = h_tf.add_paragraph()
                    h_p2.text = sc['title']
                    h_p2.font.size = Pt(11)
                    h_p2.font.bold = True
                    h_p2.font.color.rgb = RGBColor(255, 255, 255)
                    h_p2.alignment = PP_ALIGN.CENTER

                    # Content bullet list
                    s_box = slide.shapes.add_textbox(c_x + Inches(0.2), Inches(2.85), col_w - Inches(0.4), Inches(3.5))
                    s_tf = s_box.text_frame
                    s_tf.word_wrap = True

                    items_to_show = sc['items'] if sc['items'] else bullets[:2]
                    for bi, it in enumerate(items_to_show[:3]):
                        p_it = s_tf.add_paragraph() if bi > 0 else s_tf.paragraphs[0]
                        p_it.text = f"• {it}"
                        p_it.font.size = Pt(12)
                        p_it.font.color.rgb = theme['text_color']
                        if bi > 0:
                            p_it.space_before = Pt(10)

            # ── LAYOUT 2: HORIZONTAL PILL CARDS (OVERVIEW & OBJECTIVES A, B, C)
            elif slide_type == 'horizontal_pills':
                pill_items = cards if cards else [
                    { "title": "Objective A: Standardize Infrastructure & Protocol", "description": "Normalize multi-source data ingestion, enforce strict quality benchmarks, and ensure full audit compliance." },
                    { "title": "Objective B: Accelerate Operational Pipeline Velocity", "description": "Eliminate systemic handoff latency, automate verification routines, and scale processing throughput by 3.5x." },
                    { "title": "Objective C: Institutionalize Enterprise Governance", "description": "Deliver continuous executive scorecards, role-based telemetry access, and reliable longitudinal reporting." }
                ]
                item_count = min(3, len(pill_items))
                card_h = Inches(1.35)
                card_gap = Inches(0.32)
                top_start = Inches(1.7)
                letters = ['A', 'B', 'C', 'D']

                for pi in range(item_count):
                    p_data = pill_items[pi]
                    p_top = top_start + pi * (card_h + card_gap)

                    # Pill card container
                    p_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), p_top, Inches(11.733), card_h
                    )
                    p_card.fill.solid()
                    p_card.fill.fore_color.rgb = theme['card_color']
                    p_card.line.color.rgb = theme['card_border']

                    # Left accent color bar (4pt wide) — premium visual marker per pill
                    left_bar = slide.shapes.add_shape(
                        MSO_SHAPE.RECTANGLE, Inches(0.8), p_top, Inches(0.12), card_h
                    )
                    left_bar.fill.solid()
                    left_bar.fill.fore_color.rgb = theme.get('primary_accent', theme['title_color']) if pi == 0 else (
                        theme['accent_color'] if pi == 1 else RGBColor(16, 185, 129)
                    )
                    left_bar.line.fill.background()

                    # Letter Badge Circle (A, B, C)
                    badge_circle = slide.shapes.add_shape(
                        MSO_SHAPE.OVAL, Inches(1.15), p_top + Inches(0.22), Inches(0.9), Inches(0.9)
                    )
                    badge_circle.fill.solid()
                    badge_circle.fill.fore_color.rgb = theme.get('primary_accent', theme['title_color'])
                    badge_circle.line.fill.background()
                    bc_tf = badge_circle.text_frame
                    bc_p = bc_tf.paragraphs[0]
                    bc_p.text = letters[pi]
                    bc_p.font.size = Pt(20)
                    bc_p.font.bold = True
                    bc_p.font.color.rgb = RGBColor(255, 255, 255)
                    bc_p.alignment = PP_ALIGN.CENTER

                    # Text container
                    t_box = slide.shapes.add_textbox(Inches(2.3), p_top + Inches(0.18), Inches(10.0), card_h - Inches(0.36))
                    t_tf = t_box.text_frame
                    t_tf.word_wrap = True

                    p_pt = t_tf.paragraphs[0]
                    p_pt.text = p_data.get('title', f'Strategic Pillar {letters[pi]}')
                    p_pt.font.size = Pt(15.5)
                    p_pt.font.bold = True
                    p_pt.font.color.rgb = theme['title_color']

                    p_pd = t_tf.add_paragraph()
                    p_pd.text = p_data.get('description', '')
                    p_pd.font.size = Pt(12.5)
                    p_pd.font.color.rgb = theme['text_color']
                    p_pd.space_before = Pt(4)

            # ── LAYOUT 3: CIRCULAR PERCENTAGE PROGRESS DIALS ─────────────────
            elif slide_type == 'circular_dials':
                dials_list = slide_info.get('dials', [
                    { "percent": 88, "label": "Retention Rate" },
                    { "percent": 65, "label": "Market Coverage" },
                    { "percent": 94, "label": "Model Precision" }
                ])

                # Left side: Generate & Embed circular dials graphic
                try:
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_dials:
                        tmp_dials_path = tmp_dials.name
                    generate_circular_dials_graphic(dials_list, theme, tmp_dials_path)
                    slide.shapes.add_picture(tmp_dials_path, Inches(0.8), Inches(1.7), Inches(7.4), Inches(4.8))
                    try:
                        os.remove(tmp_dials_path)
                    except Exception:
                        pass
                except Exception as de:
                    logger.warning(f"Could not render circular dials graphic: {de}")

                # Right side: Strategic Insights & Telemetry Card
                right_card = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.5), Inches(1.7), Inches(4.033), Inches(4.8)
                )
                right_card.fill.solid()
                right_card.fill.fore_color.rgb = theme['card_color']
                right_card.line.color.rgb = theme['card_border']

                d_box = slide.shapes.add_textbox(Inches(8.8), Inches(2.0), Inches(3.5), Inches(4.2))
                d_tf = d_box.text_frame
                d_tf.word_wrap = True

                p_dhead = d_tf.paragraphs[0]
                p_dhead.text = "📈 TELEMETRY OBSERVATIONS"
                p_dhead.font.size = Pt(12)
                p_dhead.font.bold = True
                p_dhead.font.color.rgb = theme['accent_color']

                d_bullets = bullets if bullets else [
                    "Operational metrics indicate strong traction against targets.",
                    "Retention remains positioned well within the top decile.",
                    "Validation safeguards effectively prevent false positive triggers."
                ]
                for b_text in d_bullets[:4]:
                    pb = d_tf.add_paragraph()
                    pb.text = f"• {b_text}"
                    pb.font.size = Pt(13)
                    pb.font.color.rgb = theme['text_color']
                    pb.space_before = Pt(12)

            # ── LAYOUT 4: PROCESS CHEVRONS (STEP 1 -> STEP 2 -> STEP 3 -> STEP 4)
            elif slide_type == 'process_chevrons':
                step_items = cards if cards else [
                    { "title": "Ingestion & Audit", "description": "Baseline benchmarks, telemetry setup, and schema validation." },
                    { "title": "Core Pipeline Execution", "description": "High-throughput transformations, AI model inference, and edge testing." },
                    { "title": "Automated Quality Gates", "description": "Verification scorecards, regression checks, and failovers." },
                    { "title": "Scale & Governance", "description": "Cross-platform rollout, executive dashboards, and telemetry." }
                ]
                item_count = min(4, len(step_items))
                col_w = Inches(2.72) if item_count == 4 else Inches(3.6)
                col_gap = Inches(0.28) if item_count == 4 else Inches(0.4)
                c_left_margin = Inches(0.8)

                for si in range(item_count):
                    s_data = step_items[si]
                    c_x = c_left_margin + si * (col_w + col_gap)

                    # Card container
                    s_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE, c_x, Inches(1.7), col_w, Inches(4.8)
                    )
                    s_card.fill.solid()
                    s_card.fill.fore_color.rgb = theme['card_color']
                    s_card.line.color.rgb = theme['card_border']

                    # Chevron Header Shape
                    chev = slide.shapes.add_shape(
                        MSO_SHAPE.CHEVRON, c_x, Inches(1.7), col_w, Inches(0.75)
                    )
                    chev.fill.solid()
                    chev.fill.fore_color.rgb = theme.get('primary_accent', theme['title_color']) if si == 0 else theme['highlight_bg']
                    chev.line.fill.background()
                    ch_tf = chev.text_frame
                    ch_p = ch_tf.paragraphs[0]
                    ch_p.text = f"STEP 0{si + 1}"
                    ch_p.font.size = Pt(12)
                    ch_p.font.bold = True
                    ch_p.font.color.rgb = RGBColor(255, 255, 255) if si == 0 else theme['title_color']
                    ch_p.alignment = PP_ALIGN.CENTER

                    # Step content box
                    st_box = slide.shapes.add_textbox(c_x + Inches(0.2), Inches(2.7), col_w - Inches(0.4), Inches(3.6))
                    st_tf = st_box.text_frame
                    st_tf.word_wrap = True

                    p_stitle = st_tf.paragraphs[0]
                    p_stitle.text = s_data.get('title', f'Milestone {si+1}')
                    p_stitle.font.size = Pt(15)
                    p_stitle.font.bold = True
                    p_stitle.font.color.rgb = theme['title_color']

                    p_sdesc = st_tf.add_paragraph()
                    p_sdesc.text = s_data.get('description', '')
                    p_sdesc.font.size = Pt(12.5)
                    p_sdesc.font.color.rgb = theme['text_color']
                    p_sdesc.space_before = Pt(10)

            # ── LAYOUT 5: TEAM & PERSONA CARDS (CIRCULAR AVATARS) ────────────
            elif slide_type == 'team_personas':
                team_items = cards if cards else [
                    { "title": "Dr. Sarah Jenkins", "role": "Chief Technology Officer", "description": "15+ years leading distributed systems architecture, AI platforms, and compliance infrastructure." },
                    { "title": "Marcus Vance", "role": "Head of Product Strategy", "description": "Former McKinsey director specializing in go-to-market scaling, operating rhythm, and team growth." },
                    { "title": "Elena Rostova", "role": "Lead Systems Architect", "description": "Expert in deterministic low-latency pipelines, fault tolerance, and empirical telemetry." }
                ]
                item_count = min(3, len(team_items))
                col_w = Inches(3.6)
                col_gap = Inches(0.4)
                c_left_margin = Inches(0.8)

                for ti in range(item_count):
                    t_data = team_items[ti]
                    c_x = c_left_margin + ti * (col_w + col_gap)

                    # Member card
                    m_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE, c_x, Inches(1.7), col_w, Inches(4.8)
                    )
                    m_card.fill.solid()
                    m_card.fill.fore_color.rgb = theme['card_color']
                    m_card.line.color.rgb = theme['card_border']

                    # Circular Avatar Placeholder Badge
                    avatar = slide.shapes.add_shape(
                        MSO_SHAPE.OVAL, c_x + (col_w / 2) - Inches(0.85), Inches(2.1), Inches(1.7), Inches(1.7)
                    )
                    avatar.fill.solid()
                    avatar.fill.fore_color.rgb = theme['highlight_bg']
                    avatar.line.color.rgb = theme['accent_color']
                    avatar.line.width = Pt(2)
                    av_tf = avatar.text_frame
                    av_tf.word_wrap = False
                    # Vertical centering fix: set anchor to MIDDLE
                    if MSO_ANCHOR:
                        try:
                            av_tf.vertical_anchor = MSO_ANCHOR.MIDDLE
                        except Exception:
                            pass
                    av_p = av_tf.paragraphs[0]
                    # Initials
                    words = t_data.get('title', 'Team Member').split()
                    initials = "".join([w[0] for w in words[:2]]) if words else "TM"
                    av_p.text = initials
                    av_p.font.size = Pt(24)
                    av_p.font.bold = True
                    av_p.font.color.rgb = theme['title_color']
                    av_p.alignment = PP_ALIGN.CENTER

                    # Member Info Box
                    info_box = slide.shapes.add_textbox(c_x + Inches(0.2), Inches(4.0), col_w - Inches(0.4), Inches(2.3))
                    info_tf = info_box.text_frame
                    info_tf.word_wrap = True

                    p_name = info_tf.paragraphs[0]
                    p_name.text = t_data.get('title', 'Team Lead')
                    p_name.font.size = Pt(17)
                    p_name.font.bold = True
                    p_name.font.color.rgb = theme['title_color']
                    p_name.alignment = PP_ALIGN.CENTER

                    p_role = info_tf.add_paragraph()
                    p_role.text = t_data.get('role', 'Strategic Lead')
                    p_role.font.size = Pt(12)
                    p_role.font.bold = True
                    p_role.font.color.rgb = theme['accent_color']
                    p_role.alignment = PP_ALIGN.CENTER
                    p_role.space_before = Pt(3)

                    p_bio = info_tf.add_paragraph()
                    p_bio.text = t_data.get('description', '')
                    p_bio.font.size = Pt(11.5)
                    p_bio.font.color.rgb = theme['text_color']
                    p_bio.space_before = Pt(8)

            # ── LAYOUT 6: EDITORIAL MAGAZINE SPLIT ("SURA" STYLE) ────────────
            elif slide_type == 'editorial_split':
                # Left side: High-Resolution Curated Topic Photography
                img_path = fetch_or_create_slide_image(topic, slide_num=slide_num, theme=theme)
                if img_path and os.path.exists(img_path):
                    try:
                        slide.shapes.add_picture(img_path, Inches(0.8), Inches(1.7), Inches(5.6), Inches(4.8))
                    except Exception as ie:
                        logger.warning(f"Could not embed editorial photo: {ie}")

                # Right side: Minimalist Editorial Content Card
                right_card = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.7), Inches(1.7), Inches(5.833), Inches(4.8)
                )
                right_card.fill.solid()
                right_card.fill.fore_color.rgb = theme['card_color']
                right_card.line.color.rgb = theme['card_border']

                # Large Number Callout (e.g. 01. or 02.)
                num_box = slide.shapes.add_textbox(Inches(7.1), Inches(2.0), Inches(2.0), Inches(0.8))
                num_tf = num_box.text_frame
                num_p = num_tf.paragraphs[0]
                num_p.text = f"0{slide_num}."
                num_p.font.size = Pt(36)
                num_p.font.bold = True
                num_p.font.color.rgb = theme['accent_color']

                e_box = slide.shapes.add_textbox(Inches(7.1), Inches(2.8), Inches(5.0), Inches(3.5))
                e_tf = e_box.text_frame
                e_tf.word_wrap = True

                p_ehead = e_tf.paragraphs[0]
                p_ehead.text = "STRATEGIC NARRATIVE & SPOTLIGHT"
                p_ehead.font.size = Pt(11)
                p_ehead.font.bold = True
                p_ehead.font.color.rgb = theme['subtext_color']

                e_bullets = bullets if bullets else [
                    "Ground execution in verifiable empirical benchmarks.",
                    "Streamline operational protocols to eliminate handoff friction.",
                    "Institutionalize automated quality verification gates at scale."
                ]
                for bi, b_text in enumerate(e_bullets[:4]):
                    pb = e_tf.add_paragraph()
                    pb.text = f"{b_text}"
                    pb.font.size = Pt(14)
                    pb.font.color.rgb = theme['text_color']
                    pb.space_before = Pt(14)

            # ── LAYOUT 7: VISUAL DATA CHART SLIDE ────────────────────────────
            elif slide_type == 'chart' or 'chart_data' in slide_info:
                chart_data = slide_info.get('chart_data', {
                    'chart_type': 'bar',
                    'title': f'{topic} Empirical Metrics',
                    'labels': ['Efficiency', 'Accuracy', 'Throughput', 'Uptime'],
                    'values': [74, 91, 88, 99]
                })

                # Left side: Key bullet points & strategic focus
                left_card = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.7), Inches(5.3), Inches(4.8)
                )
                left_card.fill.solid()
                left_card.fill.fore_color.rgb = theme['card_color']
                left_card.line.color.rgb = theme['card_border']

                l_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.9), Inches(4.9), Inches(4.4))
                l_tf = l_box.text_frame
                l_tf.word_wrap = True

                p_fhead = l_tf.paragraphs[0]
                p_fhead.text = "📊 FINANCIAL & EMPIRICAL METRICS"
                p_fhead.font.size = Pt(13)
                p_fhead.font.bold = True
                p_fhead.font.color.rgb = theme['accent_color']

                chart_bullets = bullets if bullets else [
                    "Empirical validation confirms clear performance divergence.",
                    "Primary benchmarks demonstrate steady trajectory toward targets.",
                    "Measurable gains observed in automated processing efficiency."
                ]
                for b_text in chart_bullets[:4]:
                    pb = l_tf.add_paragraph()
                    pb.text = f"• {b_text}"
                    pb.font.size = Pt(14)
                    pb.font.color.rgb = theme['text_color']
                    pb.space_before = Pt(14)

                # Right side: Generate & Embed Matplotlib Visual Chart
                try:
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_chart:
                        tmp_chart_path = tmp_chart.name
                    generate_slide_visual_chart(chart_data, theme, tmp_chart_path)
                    slide.shapes.add_picture(tmp_chart_path, Inches(6.4), Inches(1.7), Inches(6.1), Inches(4.8))
                    try:
                        os.remove(tmp_chart_path)
                    except Exception:
                        pass
                except Exception as ce:
                    logger.warning(f"Could not render matplotlib visual chart: {ce}")

            # ── LAYOUT 8: VISUAL SPLIT (HIGH-RES PHOTO + STRATEGIC CARDS) ────
            elif slide_type == 'visual_split':
                left_card = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.7), Inches(6.8), Inches(4.8)
                )
                left_card.fill.solid()
                left_card.fill.fore_color.rgb = theme['card_color']
                left_card.line.color.rgb = theme['card_border']

                ac_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.1), Inches(2.0), Inches(1.5), Inches(0.06))
                ac_line.fill.solid()
                ac_line.fill.fore_color.rgb = theme['title_color']
                ac_line.line.fill.background()

                c_box = slide.shapes.add_textbox(Inches(1.1), Inches(2.2), Inches(6.2), Inches(4.1))
                c_tf = c_box.text_frame
                c_tf.word_wrap = True

                p_strat = c_tf.paragraphs[0]
                p_strat.text = "KEY STRATEGIC IMPERATIVES"
                p_strat.font.size = Pt(12)
                p_strat.font.bold = True
                p_strat.font.color.rgb = theme['accent_color']

                v_bullets = bullets if bullets else [
                    "Ground execution in verifiable empirical benchmarks.",
                    "Streamline operational protocols to eliminate handoff latency.",
                    "Institute automated quality verification gates at scale."
                ]
                for i, b_text in enumerate(v_bullets[:4]):
                    pb = c_tf.add_paragraph()
                    pb.text = f"0{i+1}.  {b_text}"
                    pb.font.size = Pt(14.5)
                    pb.font.color.rgb = theme['text_color']
                    pb.space_before = Pt(14)

                img_path = fetch_or_create_slide_image(topic, slide_num=slide_num, theme=theme)
                if img_path and os.path.exists(img_path):
                    try:
                        slide.shapes.add_picture(img_path, Inches(7.9), Inches(1.7), Inches(4.6), Inches(4.8))
                    except Exception as ie:
                        logger.warning(f"Could not embed slide photo: {ie}")

            # ── LAYOUT 9: STAT CALLOUT SPOTLIGHT (BIG NUMBERS) ───────────────
            elif slide_type == 'stat_callout' or (stat_metrics and len(stat_metrics) > 0):
                metrics = stat_metrics if stat_metrics else [
                    { "number": "94.8%", "badge": "▲ Precision", "label": "Model Validation Reliability" },
                    { "number": "3.8x", "badge": "⚡ Throughput", "label": "Processing Acceleration Factor" },
                    { "number": "100%", "badge": "🔒 Private", "label": "Local-First Architecture Compliance" }
                ]
                card_count = min(3, len(metrics))
                card_width = Inches(3.6)
                card_gap = Inches(0.4)
                left_margin = Inches(0.8)

                for mi in range(card_count):
                    m_data = metrics[mi]
                    c_left = left_margin + mi * (card_width + card_gap)

                    m_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE, c_left, Inches(1.7), card_width, Inches(4.8)
                    )
                    m_card.fill.solid()
                    m_card.fill.fore_color.rgb = theme['card_color']
                    m_card.line.color.rgb = theme['title_color'] if mi == 0 else theme['card_border']

                    pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, c_left + Inches(0.3), Inches(2.0), Inches(1.7), Inches(0.42))
                    pill.fill.solid()
                    pill.fill.fore_color.rgb = theme['badge_bg']
                    pill.line.fill.background()
                    pill_tf = pill.text_frame
                    p_pill = pill_tf.paragraphs[0]
                    p_pill.text = m_data.get('badge', '★ Metric')
                    p_pill.font.size = Pt(11)
                    p_pill.font.bold = True
                    p_pill.font.color.rgb = RGBColor(255, 255, 255)
                    p_pill.alignment = PP_ALIGN.CENTER

                    st_box = slide.shapes.add_textbox(c_left + Inches(0.3), Inches(2.65), card_width - Inches(0.6), Inches(3.0))
                    st_tf = st_box.text_frame
                    st_tf.word_wrap = True

                    p_num = st_tf.paragraphs[0]
                    p_num.text = m_data.get('number', '85%')
                    p_num.font.size = Pt(46)
                    p_num.font.bold = True
                    p_num.font.color.rgb = theme['title_color']

                    p_lbl = st_tf.add_paragraph()
                    p_lbl.text = m_data.get('label', 'Core Key Performance Indicator')
                    p_lbl.font.size = Pt(14)
                    p_lbl.font.bold = True
                    p_lbl.font.color.rgb = theme['text_color']
                    p_lbl.space_before = Pt(10)

                    # Bottom accent bar — grounds card visually on light themes
                    bottom_bar = slide.shapes.add_shape(
                        MSO_SHAPE.RECTANGLE, c_left, Inches(6.3), card_width, Inches(0.2)
                    )
                    bottom_bar.fill.solid()
                    bottom_bar.fill.fore_color.rgb = theme['accent_color']
                    bottom_bar.line.fill.background()

            # ── LAYOUT 10: TIMELINE PROCESS ──────────────────────────────────
            elif slide_type == 'timeline':
                items = cards if cards else [
                    { "title": "Phase 1: Ingestion & Baseline", "description": "Data normalization, baseline telemetry capture, and environment verification." },
                    { "title": "Phase 2: Core Execution", "description": "High-throughput processing, real-time transformations, and automated validation." },
                    { "title": "Phase 3: Rollout & Scaling", "description": "Automated reporting delivery, user onboarding, and longitudinal telemetry." }
                ]
                item_count = min(3, len(items))
                card_width = Inches(3.6)
                card_gap = Inches(0.4)
                left_margin = Inches(0.8)
                connector_y = Inches(2.18)

                # Draw horizontal connector line behind all phase cards
                connector_total_w = item_count * card_width + (item_count - 1) * card_gap
                conn_line = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE, left_margin, connector_y, connector_total_w, Inches(0.06)
                )
                conn_line.fill.solid()
                conn_line.fill.fore_color.rgb = theme['accent_color']
                conn_line.line.fill.background()

                for ti in range(item_count):
                    t_data = items[ti]
                    c_left = left_margin + ti * (card_width + card_gap)

                    t_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE, c_left, Inches(1.7), card_width, Inches(4.8)
                    )
                    t_card.fill.solid()
                    t_card.fill.fore_color.rgb = theme['card_color']
                    t_card.line.color.rgb = theme['card_border']

                    # Phase badge: colored for first, highlight_bg for rest
                    pb_color = theme.get('primary_accent', theme['title_color']) if ti == 0 else theme['highlight_bg']
                    phase_badge = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, c_left, Inches(1.7), card_width, Inches(0.6))
                    phase_badge.fill.solid()
                    phase_badge.fill.fore_color.rgb = pb_color
                    phase_badge.line.fill.background()
                    pb_tf = phase_badge.text_frame
                    pb_p = pb_tf.paragraphs[0]
                    pb_p.text = f"PHASE {ti + 1:02d}"
                    pb_p.font.size = Pt(12)
                    pb_p.font.bold = True
                    pb_p.font.color.rgb = RGBColor(255, 255, 255) if ti == 0 else theme['title_color']
                    pb_p.alignment = PP_ALIGN.CENTER

                    # Circle node on connector line
                    node_x = c_left + (card_width / 2) - Inches(0.18)
                    node = slide.shapes.add_shape(
                        MSO_SHAPE.OVAL, node_x, connector_y - Inches(0.12), Inches(0.36), Inches(0.36)
                    )
                    node.fill.solid()
                    node.fill.fore_color.rgb = theme['accent_color']
                    node.line.fill.background()

                    t_box = slide.shapes.add_textbox(c_left + Inches(0.3), Inches(2.5), card_width - Inches(0.6), Inches(3.8))
                    t_tf = t_box.text_frame
                    t_tf.word_wrap = True

                    p_ttitle = t_tf.paragraphs[0]
                    p_ttitle.text = t_data.get('title', f'Milestone {ti+1}')
                    p_ttitle.font.size = Pt(16)
                    p_ttitle.font.bold = True
                    p_ttitle.font.color.rgb = theme['title_color']

                    p_tdesc = t_tf.add_paragraph()
                    p_tdesc.text = t_data.get('description', '')
                    p_tdesc.font.size = Pt(13)
                    p_tdesc.font.color.rgb = theme['text_color']
                    p_tdesc.space_before = Pt(12)

            # ── LAYOUT 11: MULTI-COLUMN COMPARISON GRID ──────────────────────
            else:
                c_items = cards if cards else [
                    { "title": "01. Architecture Foundation", "description": "Core protocols and data pipelines designed for robust throughput and minimal overhead." },
                    { "title": "02. Verification Pipeline", "description": "Continuous validation checks enforcing strict 7 Cs consistency and high accuracy." },
                    { "title": "03. Deployment & Telemetry", "description": "Real-time delivery with live feedback loops, analytics dashboards, and cross-platform clients." }
                ]
                card_count = min(3, len(c_items))
                card_width = Inches(3.6) if card_count == 3 else Inches(5.6)
                card_gap = Inches(0.4) if card_count == 3 else Inches(0.6)
                left_margin = Inches(0.8)

                for ci in range(card_count):
                    c_data = c_items[ci]
                    c_left = left_margin + ci * (card_width + card_gap)

                    grid_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE, c_left, Inches(1.7), card_width, Inches(4.8)
                    )
                    grid_card.fill.solid()
                    grid_card.fill.fore_color.rgb = theme['card_color']
                    grid_card.line.color.rgb = theme['card_border']

                    # Numbered circular badge in top-left of card
                    badge_colors = [theme.get('primary_accent', theme['title_color']), theme['accent_color'], RGBColor(16, 185, 129)]
                    num_badge = slide.shapes.add_shape(
                        MSO_SHAPE.OVAL, c_left + Inches(0.25), Inches(1.85), Inches(0.72), Inches(0.72)
                    )
                    num_badge.fill.solid()
                    num_badge.fill.fore_color.rgb = badge_colors[ci % len(badge_colors)]
                    num_badge.line.fill.background()
                    nb_tf = num_badge.text_frame
                    nb_p = nb_tf.paragraphs[0]
                    nb_p.text = f"{ci + 1:02d}"
                    nb_p.font.size = Pt(14)
                    nb_p.font.bold = True
                    nb_p.font.color.rgb = RGBColor(255, 255, 255)
                    nb_p.alignment = PP_ALIGN.CENTER

                    c_box = slide.shapes.add_textbox(c_left + Inches(0.3), Inches(2.7), card_width - Inches(0.6), Inches(3.6))
                    c_tf = c_box.text_frame
                    c_tf.word_wrap = True

                    p_ctitle = c_tf.paragraphs[0]
                    p_ctitle.text = c_data.get('title', f'Component {ci+1}')
                    p_ctitle.font.size = Pt(16)
                    p_ctitle.font.bold = True
                    p_ctitle.font.color.rgb = theme['title_color']

                    p_cdesc = c_tf.add_paragraph()
                    p_cdesc.text = c_data.get('description', '')
                    p_cdesc.font.size = Pt(13)
                    p_cdesc.font.color.rgb = theme['text_color']
                    p_cdesc.space_before = Pt(12)

            # ── FOOTER & SLIDE NUMBER ─────────────────────────────────────────
            footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.85), Inches(11.733), Inches(0.4))
            tf_foot = footer_box.text_frame
            p_foot = tf_foot.paragraphs[0]

            footer_content = f"{confidentiality_tag}  |  {outline_data.get('presentation_title', 'Executive Deck')}"
            if show_slide_numbers:
                footer_content += f"  \u2022  {slide_num:02d} / {total_slides:02d}"  # zero-padded, handles 10+ slides
            p_foot.text = footer_content
            p_foot.font.size = Pt(9.5)
            p_foot.font.color.rgb = theme['subtext_color']

        # ── LAYOUT 12: CONCLUSION SLIDE ──────────────────────────────────────
        if slide_type == 'conclusion':
            # Full-slide accent background overlay
            accent_bg = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height
            )
            accent_bg.fill.solid()
            accent_bg.fill.fore_color.rgb = theme.get('primary_accent', theme['title_color'])
            accent_bg.line.fill.background()

            # Subtle lighter overlay at top-right (brand geometry)
            corner_accent = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_TRIANGLE,
                prs.slide_width - Inches(4.5), 0, Inches(4.5), Inches(3.2)
            )
            corner_accent.fill.solid()
            corner_accent.fill.fore_color.rgb = theme['accent_color']
            corner_accent.line.fill.background()

            # Bottom branded strip
            bottom_strip = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 0, prs.slide_height - Inches(0.9), prs.slide_width, Inches(0.9)
            )
            bottom_strip.fill.solid()
            bottom_strip.fill.fore_color.rgb = theme['accent_color']
            bottom_strip.line.fill.background()

            # Presenova brand text in bottom strip
            brand_box = slide.shapes.add_textbox(Inches(0.8), prs.slide_height - Inches(0.78), Inches(11.0), Inches(0.6))
            brand_tf = brand_box.text_frame
            brand_p = brand_tf.paragraphs[0]
            brand_p.text = f"PRESENOVA AI  |  {outline_data.get('presentation_title', 'Executive Presentation')}"
            brand_p.font.size = Pt(11)
            brand_p.font.bold = True
            brand_p.font.color.rgb = RGBColor(255, 255, 255)

            # Main title (Thank You / Key Takeaways)
            title_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.2), Inches(11.333), Inches(1.6))
            ttf = title_box.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info.get('title', 'Key Takeaways & Next Steps')
            tp.font.size = Pt(48)
            tp.font.bold = True
            tp.font.color.rgb = RGBColor(255, 255, 255)
            tp.alignment = PP_ALIGN.CENTER

            # Subtitle
            sub_text = slide_info.get('subtitle', 'Thank you for your attention.')
            sub_box = slide.shapes.add_textbox(Inches(1.0), Inches(2.9), Inches(11.333), Inches(0.6))
            stf = sub_box.text_frame
            sp = stf.paragraphs[0]
            sp.text = sub_text
            sp.font.size = Pt(18)
            sp.font.color.rgb = RGBColor(220, 240, 255)
            sp.alignment = PP_ALIGN.CENTER

            # Key takeaways bullets
            conc_bullets = slide_info.get('bullets', [])
            if conc_bullets:
                for bi, b_text in enumerate(conc_bullets[:3]):
                    bx = slide.shapes.add_textbox(Inches(2.5), Inches(3.6) + bi * Inches(0.7), Inches(8.333), Inches(0.6))
                    btf = bx.text_frame
                    bp = btf.paragraphs[0]
                    bp.text = f"{bi + 1:02d}.  {b_text}"
                    bp.font.size = Pt(15)
                    bp.font.color.rgb = RGBColor(255, 255, 255)
                    bp.alignment = PP_ALIGN.LEFT

            # Contact info (if present)
            contact = slide_info.get('contact_info', '')
            if contact:
                cbox = slide.shapes.add_textbox(Inches(1.0), Inches(6.2), Inches(11.333), Inches(0.5))
                ctf = cbox.text_frame
                cp = ctf.paragraphs[0]
                cp.text = contact
                cp.font.size = Pt(12)
                cp.font.color.rgb = RGBColor(200, 230, 255)
                cp.alignment = PP_ALIGN.CENTER

        # ── LAYOUT 13: KEY VISUAL (Full-Bleed Section Divider) ───────────────
        elif slide_type == 'key_visual':
            img_path = fetch_or_create_slide_image(topic, slide_num=slide_num, theme=theme)
            if img_path and os.path.exists(img_path):
                try:
                    slide.shapes.add_picture(img_path, 0, 0, prs.slide_width, prs.slide_height)
                except Exception as ie:
                    logger.warning(f"key_visual: Could not embed full-bleed image: {ie}")

            # Dark semi-transparent overlay
            overlay = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
            overlay.fill.solid()
            overlay.fill.fore_color.rgb = RGBColor(5, 10, 20)
            overlay.line.fill.background()
            # Approximate 60% transparency via fill XML (python-pptx workaround)
            try:
                from lxml import etree
                solidFill = overlay.fill._xPr.find(qn('a:solidFill'))
                if solidFill is not None:
                    srgb = solidFill.find(qn('a:srgbClr'))
                    if srgb is not None:
                        alpha_elem = etree.SubElement(srgb, qn('a:alpha'))
                        alpha_elem.set('val', '60000')  # 60% opacity
            except Exception:
                pass

            # Large centered section title
            kv_box = slide.shapes.add_textbox(Inches(0.8), Inches(2.5), Inches(11.733), Inches(2.5))
            kv_tf = kv_box.text_frame
            kv_tf.word_wrap = True
            kv_p = kv_tf.paragraphs[0]
            kv_p.text = slide_info.get('title', 'Section')
            kv_p.font.size = Pt(52)
            kv_p.font.bold = True
            kv_p.font.color.rgb = RGBColor(255, 255, 255)
            kv_p.alignment = PP_ALIGN.CENTER

            if slide_info.get('subtitle'):
                kv_p2 = kv_tf.add_paragraph()
                kv_p2.text = slide_info['subtitle']
                kv_p2.font.size = Pt(20)
                kv_p2.font.color.rgb = theme['accent_color']
                kv_p2.alignment = PP_ALIGN.CENTER
                kv_p2.space_before = Pt(12)

        # Speaker notes
        if slide_info.get('speaker_notes'):
            notes_slide = slide.notes_slide
            text_frame = notes_slide.notes_text_frame
            text_frame.text = slide_info.get('speaker_notes')

    # Save output file
    filename = f"presentation_{uuid.uuid4().hex[:10]}.pptx"
    filepath = os.path.join(GENERATED_FOLDER, filename)
    prs.save(filepath)
    logger.info(f"[presentation_generator] High-end executive presentation saved to {filepath}")
    return filepath
