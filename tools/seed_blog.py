"""
Seed 6 career advice blog posts and download their cover images.
Run on the server:
    sudo -u jobspace /var/www/jobspace/venv/bin/python /var/www/jobspace/tools/seed_blog.py
"""
import os, sys, django, urllib.request, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from django.core.files import File
from website.models import BlogPost

POSTS = [
    {
        "title": "5 Salary Negotiation Secrets Nobody Tells You",
        "slug": "salary-negotiation-secrets",
        "category": "salary",
        "cover_color": "#059669",
        "author": "Target JobSpace Team",
        "excerpt": "Most candidates leave serious money on the table because they negotiate wrong. Here are five moves that actually work — backed by real hiring data.",
        "body": (
            "Salary negotiation is the single highest-ROI skill in your career toolkit. "
            "A 10-minute conversation at the offer stage can put an extra half a million naira or more in your pocket every single year. "
            "Yet most candidates either skip it entirely or approach it so timidly that it makes no difference.\n\n"
            "Here is the truth: hiring managers expect you to negotiate. "
            "When you do not, they do not think you are humble — they think you do not know your value.\n\n"
            "Secret number one: never give a number first. "
            "When asked about your expected salary, respond by asking for the budgeted range first. "
            "This forces them to anchor the conversation, not you.\n\n"
            "Secret number two: anchor high with confidence. "
            "If you must name a figure, go 15 to 20 percent above your actual target. "
            "Use round numbers and speak as if the figure is completely reasonable — because it is.\n\n"
            "Secret number three: negotiate the whole package. "
            "Base salary is just one lever. Signing bonuses, remote work days, extra leave, professional development budget — "
            "all of these are on the table. When salary hits a ceiling, shift to these.\n\n"
            "Secret number four: use silence as a weapon. "
            "After stating your number, stop talking. "
            "The first person who speaks after an offer is in the weaker position.\n\n"
            "Secret number five: get competing offers. "
            "Nothing accelerates a salary conversation like a real competing offer. "
            "Even if you prefer the original company, going through interviews elsewhere gives you leverage "
            "and sharpens your sense of your own market value.\n\n"
            "The candidates who earn the most are not always the most talented. "
            "They are the ones who understand their value and have the discipline to ask for it clearly."
        ),
    },
    {
        "title": "How to Write a CV That Actually Gets Read in 2026",
        "slug": "cv-that-gets-read-2026",
        "category": "career",
        "cover_color": "#2563eb",
        "author": "Target JobSpace Team",
        "excerpt": "Hiring managers spend an average of 6 seconds on a CV before deciding yes or no. Here is exactly how to make those 6 seconds count.",
        "body": (
            "Six seconds. That is the average time a recruiter spends on a CV before deciding whether to keep reading or move on. "
            "If your CV does not immediately signal value, it is gone.\n\n"
            "The problem is that most candidates write CVs for themselves — a chronological story of where they have been. "
            "Hiring managers do not care about your story. They care about one thing: can you solve my problem?\n\n"
            "Start with a punchy professional summary. Two or three sentences maximum. "
            "Do not describe who you are — describe what you deliver. "
            "A summary that mentions a specific achievement in the first sentence makes a hiring manager sit up.\n\n"
            "Ditch the objective statement. Nobody needs to know that you seek a challenging role in a dynamic organisation. "
            "Everyone seeking a job wants that. It says nothing.\n\n"
            "Use numbers everywhere. Revenue generated, costs saved, team size managed, projects delivered, percentage improvements. "
            "Quantified achievements are the difference between a CV that reads like a job description and one that reads like a track record.\n\n"
            "Keep it to one or two pages. Three pages signals that you cannot edit yourself. "
            "For anyone under eight years of experience, one page is almost always better.\n\n"
            "File format matters more than you think. PDF is almost always the right choice — "
            "it preserves your formatting across every device and system.\n\n"
            "Finally, tailor it. A generic CV sent to every employer is a CV that speaks to no employer in particular. "
            "Five targeted applications will outperform fifty generic ones every single time."
        ),
    },
    {
        "title": "The Interview Question That Trips Everyone Up (And How to Nail It)",
        "slug": "interview-question-tell-me-about-yourself",
        "category": "interview",
        "cover_color": "#7c3aed",
        "author": "Target JobSpace Team",
        "excerpt": "Tell me about yourself. It sounds simple. It ruins more interviews than any technical question. Here is the formula that works every time.",
        "body": (
            "Tell me about yourself is the most dangerous question in any interview. "
            "Not because it is hard — but because it sounds easy, so candidates never prepare for it properly.\n\n"
            "Most people respond with one of two disasters. "
            "The first is the life story — a long chronological journey that leaves the interviewer mentally checked out. "
            "The second is the CV recitation: reading back what is already on the paper in front of them.\n\n"
            "Here is the formula that actually works. We call it Present, Past, Future.\n\n"
            "Present: Start with where you are now and what you are good at. Keep it to two sentences. "
            "State your title, years of experience, and one thing you deliver.\n\n"
            "Past: Then go back to explain how you got there. Focus on one or two specific achievements — not responsibilities. "
            "A number is worth a thousand words here.\n\n"
            "Future: Finish by connecting your past and present to why you want this specific role. "
            "Show that you chose this company deliberately.\n\n"
            "The whole answer should take 90 seconds. No more. "
            "Practice it out loud until it feels conversational, not rehearsed.\n\n"
            "This structure positions you as a professional, proves you can communicate clearly, "
            "and immediately establishes that you are a relevant candidate for this specific role."
        ),
    },
    {
        "title": "Remote Work Is Here to Stay — How to Actually Thrive in It",
        "slug": "how-to-thrive-remote-work",
        "category": "workplace",
        "cover_color": "#0891b2",
        "author": "Target JobSpace Team",
        "excerpt": "Remote work has separated high performers from everyone else. The gap is not about discipline — it is about a few counterintuitive habits most people never figure out.",
        "body": (
            "Remote work does not make people lazy. It makes the gap between high performers and average performers impossible to hide.\n\n"
            "In an office, proximity creates the illusion of productivity. You are seen. You attend meetings. You look busy. "
            "Remote work strips all of that away and leaves only one thing: output.\n\n"
            "The single biggest mistake remote workers make is treating remote work like office work from home. It is not.\n\n"
            "Visibility is now your responsibility. In an office, your manager sees you. "
            "Remotely, you are invisible unless you make yourself visible. "
            "This means proactive communication — brief, frequent updates on what you are working on.\n\n"
            "Async communication is a skill. The ability to write a message that does not require a reply, "
            "that gives enough context for the reader to act without a meeting — "
            "that skill will get you promoted faster than almost anything else in a remote environment.\n\n"
            "Your environment is a productivity multiplier. A dedicated workspace, a consistent start time, a shutdown ritual — "
            "these are not optional wellness advice. They are operational requirements.\n\n"
            "Over-communicate your wins. In an office, people notice. Remotely, they do not, unless you tell them. "
            "It is not bragging — it is making sure your work is seen.\n\n"
            "Remote work done well is genuinely liberating. "
            "But it requires deliberate habits that most people never build because nobody told them it was necessary."
        ),
    },
    {
        "title": "Why Nigerian Graduates Are Getting Rejected (And How to Fix It)",
        "slug": "why-nigerian-graduates-getting-rejected",
        "category": "career",
        "cover_color": "#d97706",
        "author": "Target JobSpace Team",
        "excerpt": "The Nigerian job market is brutally competitive and most graduates are making the same five mistakes. Here is the honest breakdown — and the fix.",
        "body": (
            "The Nigerian graduate job market is one of the most competitive in Africa. "
            "Millions of graduates chasing tens of thousands of quality roles. "
            "And yet the same avoidable mistakes show up again and again.\n\n"
            "Mistake one: generic applications. Sending the same CV to 50 companies is not a strategy. "
            "It is hope cosplaying as effort. Employers can tell immediately when an application was not written with them in mind.\n\n"
            "Mistake two: treating NYSC as a gap. Your service year is not a pause — "
            "it is a twelve-month opportunity to build something. Use it.\n\n"
            "Mistake three: waiting to be ready. The perfect moment does not come. "
            "Start now with what you have.\n\n"
            "Mistake four: ignoring soft skills entirely. Nigeria's universities produce technically sound graduates. "
            "But communication, stakeholder management, the ability to write a clear email — "
            "these are the skills that determine who gets promoted. They are learnable.\n\n"
            "Mistake five: not networking because it feels uncomfortable. "
            "In a relationship-driven market like Nigeria, who you know genuinely matters. "
            "Build relationships before you need them.\n\n"
            "The graduates who break through are not always the most qualified. "
            "They are the most prepared, the most visible, and the most consistent."
        ),
    },
    {
        "title": "The Hidden Job Market: 70% of Roles Are Never Advertised",
        "slug": "hidden-job-market-unadvertised-roles",
        "category": "hiring",
        "cover_color": "#dc2626",
        "author": "Target JobSpace Team",
        "excerpt": "Most jobs are never posted publicly. The companies that hire through platforms like Target JobSpace fill roles faster, quieter, and with better candidates. Here is how to tap into that.",
        "body": (
            "Between 60 and 80 percent of job vacancies are filled before they are ever advertised publicly. "
            "That number should fundamentally change how you approach your job search.\n\n"
            "The roles you see on job boards — the ones with 400 applications in 48 hours — "
            "are the ones nobody could fill any other way. "
            "The best roles, at the best companies, are filled quietly, before any public announcement is made.\n\n"
            "Why do companies do this? Because public posting is expensive and produces a huge volume of "
            "low-quality applications. When a trusted platform delivers five pre-vetted candidates, "
            "a company will choose that every time over a pile of 300 unreviewed CVs.\n\n"
            "How do you access this hidden market?\n\n"
            "First, get on the right platforms. Specialist platforms that vet candidates before presenting them to employers "
            "are the front door to the hidden market. Your profile on those platforms works for you "
            "even when you are not actively looking.\n\n"
            "Second, build relationships with people who make hiring decisions. "
            "Not just HR — line managers and department heads who know what roles are opening before HR even knows.\n\n"
            "Third, approach companies directly. Research organisations you want to work for and reach out "
            "before they have a vacancy. A well-crafted, specific speculative approach from a qualified candidate is rarely ignored.\n\n"
            "The job seekers who find the best opportunities the fastest are not necessarily the most talented. "
            "They are the most visible to the right people at the right time."
        ),
    },
]

# ── Create posts ──────────────────────────────────────────────────────────────
created = 0
for p in POSTS:
    if not BlogPost.objects.filter(slug=p["slug"]).exists():
        BlogPost.objects.create(**p)
        created += 1
        print(f"  Created: {p['slug']}")
    else:
        print(f"  Already exists: {p['slug']}")

print(f"\nSeeded {created} new posts. Total: {BlogPost.objects.count()}")

# ── Download cover images ─────────────────────────────────────────────────────
COVER_IMAGES = {
    "salary-negotiation-secrets":                ("https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=800&q=80", "salary.jpg"),
    "cv-that-gets-read-2026":                    ("https://images.unsplash.com/photo-1586281380349-632531db7ed4?w=800&q=80", "cv.jpg"),
    "interview-question-tell-me-about-yourself": ("https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=800&q=80", "interview.jpg"),
    "how-to-thrive-remote-work":                 ("https://images.unsplash.com/photo-1587614382346-4ec70e388b28?w=800&q=80", "remote.jpg"),
    "why-nigerian-graduates-getting-rejected":    ("https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=800&q=80", "graduates.jpg"),
    "hidden-job-market-unadvertised-roles":       ("https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&q=80", "jobs.jpg"),
}

print("\nDownloading cover images...")
for slug, (url, fname) in COVER_IMAGES.items():
    try:
        post = BlogPost.objects.get(slug=slug)
        if post.cover_image:
            print(f"  SKIP (already has image): {slug}")
            continue
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            urllib.request.urlretrieve(url, tmp.name)
            with open(tmp.name, "rb") as f:
                post.cover_image.save(fname, File(f), save=True)
            os.unlink(tmp.name)
        print(f"  OK: {slug}")
    except Exception as e:
        print(f"  ERR {slug}: {e}")

print("\nFinal state:")
for p in BlogPost.objects.all():
    img = p.cover_image.name if p.cover_image else "NO IMAGE"
    print(f"  {p.slug[:50]:<50}  {img}")
