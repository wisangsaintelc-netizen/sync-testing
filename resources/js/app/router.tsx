import { createBrowserRouter, Navigate, Outlet, useLocation } from 'react-router-dom';
import { getToken } from '@/api/client';
import { AppShell } from '@/layout/AppShell';
import { Dashboard } from '@/views/dashboard/Dashboard';
import { Agents } from '@/views/agents/Agents';
import { Assign } from '@/views/assign/Assign';
import { Runs } from '@/views/runs/Runs';
import { Audit } from '@/views/audit/Audit';
import { Clients } from '@/views/clients/Clients';
import { Catalog } from '@/views/catalog/Catalog';
import { Login } from '@/views/login/Login';

function RequireAuth() {
    const location = useLocation();
    if (!getToken()) {
        return <Navigate to="/login" state={{ from: location.pathname }} replace />;
    }
    return <Outlet />;
}

export const router = createBrowserRouter([
    { path: '/login', element: <Login /> },
    {
        element: <RequireAuth />,
        children: [
            {
                element: <AppShell />,
                children: [
                    { path: '/', element: <Dashboard /> },
                    { path: '/agents', element: <Agents /> },
                    { path: '/agents/assign', element: <Assign /> },
                    { path: '/agents/assign/:agentCode', element: <Assign /> },
                    { path: '/runs', element: <Runs /> },
                    { path: '/audit', element: <Audit /> },
                    { path: '/clients', element: <Clients /> },
                    { path: '/catalog', element: <Catalog /> },
                    { path: '*', element: <Navigate to="/" replace /> },
                ],
            },
        ],
    },
]);
