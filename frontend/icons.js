// Outline icon geometry based on Tabler Icons, MIT license. See docs/asset-credits.md.
const paths = {
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  home: '<path d="m3 10 9-7 9 7v10H3zM9 20v-7h6v7"/>',
  subscriptions: '<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M7 3h10M5 5h14m-4 9-5-3v6z"/>',
  play: '<path d="m9 5 11 7-11 7z"/>',
  upload: '<path d="M4 16v4h16v-4M12 16V3m-5 5 5-5 5 5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v2"/>',
  like: '<path d="M7 10v11H3V10zm0 0 5-7c2 0 2 3 1 6h6a2 2 0 0 1 2 2l-2 8a2 2 0 0 1-2 2H7"/>',
  list: '<path d="M4 5h13M4 10h13M4 15h7m4-1 6 4-6 4z"/>',
  studio: '<path d="m12 3 9 5v9l-9 5-9-5V8zm-3 5 7 4-7 4z"/>',
  flag: '<path d="M5 21V3m0 0h14l-3 4 3 4H5"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM9 12l2 2 4-4"/>',
  logout: '<path d="M10 4H4v16h6m-1-8h12m-4-4 4 4-4 4"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  more: '<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
  globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
  edit: '<path d="m16 3 5 5L8 21H3v-5zm-2 2 5 5"/>',
  share: '<path d="m13 4 8 7-8 7v-4c-5 0-8 2-10 6 0-8 4-11 10-11z"/>',
  bell: '<path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5zM10 21h4"/>',
};
export function icon(name, cls = '') {
  return `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.play}</svg>`;
}
