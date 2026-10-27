import { Link, useLocation } from 'react-router-dom';
import { IconChevronRight } from '@/components/icons';

type BreadcrumbItem = {
    label: string;
    to?: string;
};

const BREADCRUMBS: Record<string, BreadcrumbItem[]> = {
    '/': [{ label: 'Inicio' }],
    '/agents': [
        { label: 'Inicio', to: '/' },
        { label: 'Listado' },
    ],
    '/agents/assign': [
        { label: 'Inicio', to: '/' },
        { label: 'Asignación' },
    ],
    '/runs': [
        { label: 'Inicio', to: '/' },
        { label: 'Ejecuciones' },
    ],
    '/audit': [
        { label: 'Inicio', to: '/' },
        { label: 'Auditoría' },
    ],
    '/clients': [
        { label: 'Inicio', to: '/' },
        { label: 'Clientes' },
    ],
    '/catalog': [
        { label: 'Inicio', to: '/' },
        { label: 'Catálogo de sincronizadores' },
    ],
};

export function Breadcrumbs() {
    const { pathname } = useLocation();
    const selectedAssignment = /^\/agents\/assign\/([^/]+)$/.exec(pathname);
    const items = selectedAssignment
        ? [
            { label: 'Inicio', to: '/' },
            { label: 'Asignación', to: '/agents/assign' },
            { label: decodeURIComponent(selectedAssignment[1]) },
        ]
        : BREADCRUMBS[pathname] ?? BREADCRUMBS['/'];

    return (
        <nav className="breadcrumbs" aria-label="Ruta de navegación">
            <ol className="breadcrumbs__list">
                {items.map((item, index) => {
                    const isCurrent = index === items.length - 1;

                    return (
                        <li className="breadcrumbs__item" key={`${item.label}-${index}`}>
                            {index > 0 && <IconChevronRight className="breadcrumbs__separator" size={13} />}
                            {item.to && !isCurrent ? (
                                <Link className="breadcrumbs__link" to={item.to}>{item.label}</Link>
                            ) : (
                                <span className={isCurrent ? 'breadcrumbs__current' : 'breadcrumbs__context'} aria-current={isCurrent ? 'page' : undefined}>
                                    {item.label}
                                </span>
                            )}
                        </li>
                    );
                })}
            </ol>
        </nav>
    );
}
