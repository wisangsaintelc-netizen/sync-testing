import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { IconBurger, IconRefresh, IconSearch } from '@/components/icons';

const TITLES: Record<string, { title: string; subtitle: string }> = {
    '/': { title: 'Dashboard operativo', subtitle: 'Monitoreo en tiempo real' },
    '/agents': { title: 'Agentes', subtitle: 'Listado y estado de agentes instalados' },
    '/agents/assign': { title: 'Asignación de sincronizadores', subtitle: 'Permisos e intervalos por agente' },
    '/runs': { title: 'Ejecuciones', subtitle: 'Historial y manejo de errores' },
    '/audit': { title: 'Auditoría', subtitle: 'Trazabilidad de comandos, eventos y accesos' },
    '/clients': { title: 'Clientes', subtitle: 'Negocios con sincronización BAPPS' },
    '/catalog': { title: 'Catálogo de sincronizadores', subtitle: 'Definiciones disponibles para asignar' },
};

export function Topbar({ onBurger }: { onBurger: () => void }) {
    const location = useLocation();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [q, setQ] = useState('');
    const [spinning, setSpinning] = useState(false);

    const heading = TITLES[location.pathname] ?? TITLES['/'];

    const submitSearch = () => {
        const target = location.pathname === '/' ? '/agents' : location.pathname;
        navigate(`${target}?search=${encodeURIComponent(q)}`);
    };

    const refresh = () => {
        setSpinning(true);
        void queryClient.invalidateQueries();
        setTimeout(() => setSpinning(false), 900);
    };

    return (
        <header className="topbar">
            <button className="topbar__burger" onClick={onBurger} aria-label="Abrir menú">
                <IconBurger size={18} />
            </button>
            <div className="topbar__heading">
                <div className="topbar__title">{heading.title}</div>
                <div className="topbar__subtitle">{heading.subtitle}</div>
            </div>
            <label className="topbar__search">
                <IconSearch size={14} />
                <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') submitSearch();
                    }}
                    placeholder="Buscar agente, cliente, run_id…"
                />
            </label>
            <div className="topbar__env">
                <span className="topbar__env-dot" />
                PROD
            </div>
            <button
                className={`topbar__refresh${spinning ? ' topbar__refresh--spinning' : ''}`}
                onClick={refresh}
                aria-label="Refrescar"
                title="Refrescar"
            >
                <IconRefresh size={15} />
            </button>
        </header>
    );
}
