# -*- coding: utf-8 -*-
"""Re-theme: dark red + alternating black/white sections."""
import pathlib
base = pathlib.Path('c:/Users/ADMIN/Desktop/JOB TARGET SPACE')

def load(name):
    return (base / name).read_text(encoding='utf-8')  # universal newlines -> \n

def save(name, text):
    (base / name).write_text(text, encoding='utf-8', newline='\n')

P = []  # (file, old, new, expected_count)  expected -1 = >=1, 0 = optional
def add(f, old, new, n=-1): P.append((f, old, new, n))

S, G = 'css/style.css', 'css/pages.css'

# ============ style.css : tokens ============
add(S, "  --red:#ec0644;\n  --red-hover:#ff1e5a;\n  --red-deep:#c40038;\n  --red-glow:rgba(236,6,68,.45);",
        "  --red:#b3071b;\n  --red-hover:#d10a20;\n  --red-deep:#7e0412;\n  --red-glow:rgba(179,7,27,.5);\n  --red-bright:#d60a22;")

# ============ style.css : brands -> BLACK ============
add(S, ".brands{padding:38px 0 34px;background:#f7f7f8;border-bottom:1px solid rgba(10,10,10,.07)}",
        ".brands{padding:38px 0 34px;background:#0b0b0b;border-bottom:1px solid rgba(255,255,255,.09)}")
add(S, ".brands>strong{display:block;text-align:center;font:700 11px 'Montserrat',sans-serif;letter-spacing:3.5px;color:rgba(15,15,15,.45);text-transform:uppercase;margin-bottom:22px}",
        ".brands>strong{display:block;text-align:center;font:700 11px 'Montserrat',sans-serif;letter-spacing:3.5px;color:rgba(255,255,255,.5);text-transform:uppercase;margin-bottom:22px}")
add(S, ".brand-track span{font:700 18px 'Montserrat',sans-serif;color:rgba(15,15,15,.45);white-space:nowrap;transition:color .3s}",
        ".brand-track span{font:700 18px 'Montserrat',sans-serif;color:rgba(255,255,255,.55);white-space:nowrap;transition:color .3s}")
add(S, ".brand-track span:hover{color:#0d0d0d}", ".brand-track span:hover{color:#fff}")

# ============ style.css : find -> BLACK ============
add(S, ".find{background:#f7f7f8;border-bottom:1px solid rgba(10,10,10,.07)}",
        ".find{background:#0b0b0b;border-bottom:1px solid rgba(255,255,255,.07)}")
add(S, ".feature h2{font-size:clamp(26px,2.6vw,34px);font-weight:800;margin-bottom:14px}",
        ".feature h2{font-size:clamp(26px,2.6vw,34px);font-weight:800;margin-bottom:14px;color:#fff}")

# ============ style.css : jobs -> BLACK ============
add(S, ".jobs{background:#ffffff;border-top:1px solid rgba(10,10,10,.06);border-bottom:1px solid rgba(10,10,10,.07)}",
        ".jobs{background:#0b0b0b;border-top:1px solid rgba(255,255,255,.07);border-bottom:1px solid rgba(255,255,255,.07)}")
add(S, ".jobs-intro h2{font-size:clamp(30px,3.6vw,46px);font-weight:800;margin-bottom:8px}",
        ".jobs-intro h2{font-size:clamp(30px,3.6vw,46px);font-weight:800;margin-bottom:8px;color:#fff}")
add(S, "scrollbar-color:rgba(236,6,68,.5) rgba(10,10,10,.06)",
        "scrollbar-color:rgba(179,7,27,.6) rgba(255,255,255,.1)")
add(S, ".job-list::-webkit-scrollbar-track{background:rgba(10,10,10,.06);border-radius:5px}",
        ".job-list::-webkit-scrollbar-track{background:rgba(255,255,255,.08);border-radius:5px}")
add(S, ".job-list header small{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:#0d0d0d}",
        ".job-list header small{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:#fff}")
add(S, ".job-list header>span{color:rgba(15,15,15,.4);font-size:15px}",
        ".job-list header>span{color:rgba(255,255,255,.45);font-size:15px}")
add(S, ".job-list h4{font-size:17px;font-weight:700;margin-bottom:9px;line-height:1.3}",
        ".job-list h4{font-size:17px;font-weight:700;margin-bottom:9px;line-height:1.3;color:#fff}")
add(S, ".job-tags span{font-size:10.5px;padding:5px 12px;border-radius:999px;color:rgba(15,15,15,.65);background:rgba(10,10,10,.05);border:1px solid rgba(10,10,10,.1)}",
        ".job-tags span{font-size:10.5px;padding:5px 12px;border-radius:999px;color:rgba(255,255,255,.72);background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.13)}")
add(S, ".salary{display:block;font-size:15px;font-weight:700;color:#0d0d0d;margin-bottom:15px}",
        ".salary{display:block;font-size:15px;font-weight:700;color:#fff;margin-bottom:15px}")
add(S, ".job-list footer{display:flex;justify-content:space-between;align-items:center;padding-top:14px;border-top:1px solid rgba(10,10,10,.08)}",
        ".job-list footer{display:flex;justify-content:space-between;align-items:center;padding-top:14px;border-top:1px solid rgba(255,255,255,.1)}")
#__B__
