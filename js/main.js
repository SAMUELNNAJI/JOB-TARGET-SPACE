const menu = document.querySelector('.menu');
const nav = document.querySelector('nav');
const navOverlay = document.querySelector('.nav-overlay');
function setMenu(open) {
  nav.classList.toggle('open', open);
  navOverlay?.classList.toggle('open', open);
  menu?.setAttribute('aria-expanded', open);
  document.body.style.overflow = open ? 'hidden' : '';
}
menu?.addEventListener('click', () => setMenu(!nav.classList.contains('open')));
navOverlay?.addEventListener('click', () => setMenu(false));
document.addEventListener('keydown', e => { if (e.key === 'Escape') setMenu(false); });
nav?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setMenu(false)));
const backToTop = document.querySelector('.up');
backToTop?.addEventListener('click', e => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); });
window.addEventListener('scroll', () => document.querySelector('.nav')?.classList.toggle('scrolled', window.scrollY > 10));

const slides = [...document.querySelectorAll('.hero-slide')];
const count = document.querySelector('.slide-count b');
const bar = document.querySelector('.progress i');
let current = 0, timer;
function showSlide(index) {
  const next = (index + slides.length) % slides.length;
  if (next === current && slides[current].classList.contains('active')) return;
  slides[current]?.classList.remove('active'); current = next;
  slides[current].classList.add('active'); count.textContent = `0${current + 1}`;
  if (window.gsap) {
    gsap.fromTo(slides[current].querySelector('.hero-content'), { y: 35, opacity: 0 }, { y: 0, opacity: 1, duration: .85, delay: .18, ease: 'power3.out' });
    gsap.fromTo(bar, { width: 0 }, { width: `${(current + 1) * (100 / slides.length)}%`, duration: .7, ease: 'power2.out' });
  } else bar.style.width = `${(current + 1) * (100 / slides.length)}%`;
  clearInterval(timer); timer = setInterval(() => showSlide(current + 1), 6500);
}
document.querySelector('.left')?.addEventListener('click', () => showSlide(current - 1));
document.querySelector('.right')?.addEventListener('click', () => showSlide(current + 1));

if (window.gsap) {
  gsap.registerPlugin(ScrollTrigger);
  gsap.from('.nav', { y: -80, opacity: 0, duration: .8, ease: 'power3.out' });
  gsap.from('.hero .hero-content > *', { y: 28, opacity: 0, stagger: .12, duration: .7, delay: .3, ease: 'power3.out' });
  gsap.utils.toArray('.stats article, .feature, .steps article, .job-list article, .testimonials article').forEach(card => gsap.from(card, { scrollTrigger: { trigger: card, start: 'top 89%' }, y: 35, opacity: 0, duration: .65, ease: 'power2.out' }));
  gsap.to('.hero-quote', { y: -12, rotate: -6, duration: 2.6, repeat: -1, yoyo: true, ease: 'sine.inOut' });
  gsap.utils.toArray('.stats b').forEach(el => {
    const target = el.textContent;
    const isSupport = target === '24/7';
    const number = isSupport ? 24 : parseInt(target.replace(/\D/g, ''), 10);
    const suffix = isSupport ? '/7' : target.replace(/[0-9,]/g, '');
    const counter = { value: 0 };
    gsap.to(counter, { value: number, duration: 2, ease: 'power2.out', scrollTrigger: { trigger: el, start: 'top 88%', once: true }, onUpdate() { el.textContent = Math.round(counter.value).toLocaleString() + suffix; } });
  });
}
timer = setInterval(() => showSlide(current + 1), 6500);

// Featured jobs: move attention to the next card every five seconds.
const jobList = document.querySelector('.job-list');
const jobCards = jobList ? [...jobList.querySelectorAll('article')] : [];
let featuredJob = 0;
function featureJob(index) {
  if (!jobCards.length) return;
  featuredJob = index % jobCards.length;
  jobCards.forEach((card, i) => card.classList.toggle('is-featured', i === featuredJob));
  const card = jobCards[featuredJob];
  const listRect = jobList.getBoundingClientRect();
  const cardRect = card.getBoundingClientRect();
  const cardOffset = jobList.scrollLeft + (cardRect.left - listRect.left);
  const centeredLeft = cardOffset - ((jobList.clientWidth - card.offsetWidth) / 2);
  const maxScroll = jobList.scrollWidth - jobList.clientWidth;
  jobList.scrollTo({ left: Math.min(Math.max(0, centeredLeft), maxScroll), behavior: 'smooth' });
}
if (jobCards.length) {
  featureJob(0);
  setInterval(() => featureJob(featuredJob + 1), 5000);
  jobCards.forEach((card, index) => card.addEventListener('mouseenter', () => featureJob(index)));
}
