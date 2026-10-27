import { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getDashboardMetrics } from '@/api/endpoints';
import {
    IconAgents,
    IconAssign,
    IconAudit,
    IconCatalog,
    IconChevron,
    IconClients,
    IconDashboard,
    IconList,
    IconRuns,
} from '@/components/icons';

interface SidebarProps {
    open: boolean;
    onNavigate: () => void;
}

export function Sidebar({ open, onNavigate }: SidebarProps) {
    const location = useLocation();
    const navigate = useNavigate();
    const inAgents = location.pathname.startsWith('/agents');
    const [agentsOpen, setAgentsOpen] = useState(inAgents);

    // Contadores de la nav (mismos datos que el dashboard; cache compartida).
    const { data: metrics } = useQuery({
        queryKey: ['dashboard', 'metrics'],
        queryFn: getDashboardMetrics,
        refetchInterval: 15_000,
    });

    const item = (to: string, icon: React.ReactNode, label: string, count?: number) => (
        <NavLink
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-item${isActive ? ' nav-item--active' : ''}`}
            onClick={onNavigate}
        >
            <span className="nav-item__icon">{icon}</span>
            {label}
            {count !== undefined && count > 0 && <span className="nav-item__count">{count}</span>}
        </NavLink>
    );

    return (
        <aside className={`sidebar${open ? ' sidebar--open' : ''}`}>
            <div className="sidebar__brand" role="button" style={{ cursor: 'pointer' }} onClick={() => navigate('/')}>
                <div className="sidebar__logo">
                    <IconRuns size={18} />
                </div>
                <div>
                    <div className="sidebar__title">
                        <span style={{ color: '#56ACDE' }}>B</span>APPS Sync
                    </div>
                    <div className="sidebar__subtitle">Centro de operaciones</div>
                </div>
            </div>

            <nav className="sidebar__nav">
                <div className="sidebar__group">Operación</div>
                {item('/', <IconDashboard size={16} />, 'Dashboard')}

                <button className={`nav-item${inAgents ? ' nav-item--active' : ''}`} onClick={() => setAgentsOpen(!agentsOpen)}>
                    <span className="nav-item__icon"><IconAgents size={16} /></span>
                    Agentes
                    {metrics && <span className="nav-item__count">{metrics.agents_total}</span>}
                    <span className={`nav-item__chevron${agentsOpen ? ' nav-item__chevron--open' : ''}`}>
                        <IconChevron size={13} />
                    </span>
                </button>
                {agentsOpen && (
                    <div className="nav-sub">
                        {item('/agents', <IconList size={15} />, 'Listado')}
                        {item('/agents/assign', <IconAssign size={15} />, 'Asignación')}
                    </div>
                )}

                {item('/runs', <IconRuns size={16} />, 'Ejecuciones', metrics?.failed_runs_24h)}
                {item('/audit', <IconAudit size={16} />, 'Auditoría')}

                <div className="sidebar__group">Configuración</div>
                {item('/clients', <IconClients size={16} />, 'Clientes')}
                {item('/catalog', <IconCatalog size={16} />, 'Catálogo de syncs')}
            </nav>

            <div className="sidebar__footer">
                <div className="sidebar__avatar">SO</div>
                <div className="sidebar__user">
                    <div className="sidebar__user-name">Soporte BAPPS</div>
                    <div className="sidebar__user-mail">soporte@bapps.io</div>
                </div>
            </div>
        </aside>
    );
}
