import { useEffect, useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Breadcrumbs } from './Breadcrumbs';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export function AppShell() {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const navigate = useNavigate();

    // 401 desde cualquier request → volver a login.
    useEffect(() => {
        const onUnauthorized = () => navigate('/login', { replace: true });
        window.addEventListener('bapps:unauthorized', onUnauthorized);
        return () => window.removeEventListener('bapps:unauthorized', onUnauthorized);
    }, [navigate]);

    return (
        <div className="shell">
            <Sidebar open={sidebarOpen} onNavigate={() => setSidebarOpen(false)} />
            {sidebarOpen && <div className="scrim" style={{ zIndex: 39 }} onClick={() => setSidebarOpen(false)} />}
            <div className="main">
                <Topbar onBurger={() => setSidebarOpen(true)} />
                <Breadcrumbs />
                <main className="content">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}
