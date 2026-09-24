const dashboardMenu = document.querySelector('.dashboard-mobile-menu');
const dashboardSidebar = document.querySelector('.dashboard-sidebar');

dashboardMenu?.addEventListener('click', () => {
  dashboardSidebar?.classList.toggle('open');
});

document.addEventListener('click', event => {
  if (!dashboardSidebar?.classList.contains('open')) return;
  if (!dashboardSidebar.contains(event.target) && !dashboardMenu?.contains(event.target)) {
    dashboardSidebar.classList.remove('open');
  }
});

const dashboardLinks = [...document.querySelectorAll('.dashboard-nav a[href]')];
const activeDashboardLink = dashboardLinks
  .filter(link => {
    const linkPath = new URL(link.href, window.location.origin).pathname;
    return window.location.pathname === linkPath || window.location.pathname.startsWith(linkPath);
  })
  .sort((firstLink, secondLink) => secondLink.pathname.length - firstLink.pathname.length)[0];

if (activeDashboardLink) {
  dashboardLinks.forEach(link => link.classList.remove('active'));
  activeDashboardLink.classList.add('active');
}

document.querySelectorAll('[data-dashboard-action]').forEach(button => {
  button.addEventListener('click', () => {
    button.classList.toggle('is-active');
  });
});
