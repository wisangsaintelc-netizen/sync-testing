/** Set de íconos SVG inline (stroke 1.7, 24×24 viewBox, tamaño por prop). */

interface IconProps {
    size?: number;
    className?: string;
}

function base(size: number | undefined, className: string | undefined, children: React.ReactNode) {
    return (
        <svg
            width={size ?? 16}
            height={size ?? 16}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={className}
            aria-hidden="true"
        >
            {children}
        </svg>
    );
}

export const IconDashboard = (p: IconProps) => base(p.size, p.className, <><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></>);
export const IconAgents = (p: IconProps) => base(p.size, p.className, <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></>);
export const IconRuns = (p: IconProps) => base(p.size, p.className, <><polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" /></>);
export const IconAudit = (p: IconProps) => base(p.size, p.className, <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="9" y1="13" x2="15" y2="13" /><line x1="9" y1="17" x2="13" y2="17" /></>);
export const IconClients = (p: IconProps) => base(p.size, p.className, <><path d="M3 21V8l9-5 9 5v13" /><path d="M9 21v-6h6v6" /></>);
export const IconCatalog = (p: IconProps) => base(p.size, p.className, <><path d="M12 2 2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" /></>);
export const IconList = (p: IconProps) => base(p.size, p.className, <><line x1="9" y1="6" x2="20" y2="6" /><line x1="9" y1="12" x2="20" y2="12" /><line x1="9" y1="18" x2="20" y2="18" /><circle cx="4.5" cy="6" r="0.7" fill="currentColor" /><circle cx="4.5" cy="12" r="0.7" fill="currentColor" /><circle cx="4.5" cy="18" r="0.7" fill="currentColor" /></>);
export const IconAssign = (p: IconProps) => base(p.size, p.className, <><circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="6" r="2.5" /><circle cx="12" cy="18" r="2.5" /><path d="M8 7.5 10.5 15M16 7.5 13.5 15" /></>);
export const IconSearch = (p: IconProps) => base(p.size, p.className, <><circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.5" y2="16.5" /></>);
export const IconRefresh = (p: IconProps) => base(p.size, p.className, <><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>);
export const IconClose = (p: IconProps) => base(p.size, p.className, <><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></>);
export const IconChevron = (p: IconProps) => base(p.size, p.className, <polyline points="6 9 12 15 18 9" />);
export const IconChevronRight = (p: IconProps) => base(p.size, p.className, <polyline points="9 6 15 12 9 18" />);
export const IconInfo = (p: IconProps) => base(p.size, p.className, <><circle cx="12" cy="12" r="9" /><line x1="12" y1="11" x2="12" y2="16" /><circle cx="12" cy="8" r="0.4" fill="currentColor" /></>);
export const IconAlert = (p: IconProps) => base(p.size, p.className, <><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><circle cx="12" cy="16.5" r="0.4" fill="currentColor" /></>);
export const IconBurger = (p: IconProps) => base(p.size, p.className, <><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" /></>);
export const IconPlay = (p: IconProps) => base(p.size, p.className, <polygon points="6 3 20 12 6 21 6 3" />);
export const IconStop = (p: IconProps) => base(p.size, p.className, <rect x="5" y="5" width="14" height="14" rx="2" />);
export const IconPause = (p: IconProps) => base(p.size, p.className, <><line x1="9" y1="5" x2="9" y2="19" /><line x1="15" y1="5" x2="15" y2="19" /></>);
export const IconPlus = (p: IconProps) => base(p.size, p.className, <><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></>);
export const IconBolt = (p: IconProps) => base(p.size, p.className, <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />);
