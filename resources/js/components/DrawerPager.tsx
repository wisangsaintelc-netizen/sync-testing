const DRAWER_PAGE_SIZE = 10;

export function paginateDrawerItems<T>(items: T[], page: number) {
    const pages = Math.max(1, Math.ceil(items.length / DRAWER_PAGE_SIZE));
    const currentPage = Math.min(Math.max(page, 1), pages);
    const from = (currentPage - 1) * DRAWER_PAGE_SIZE;

    return {
        currentPage,
        items: items.slice(from, from + DRAWER_PAGE_SIZE),
        pages,
    };
}

interface DrawerPagerProps {
    page: number;
    pages: number;
    total: number;
    onPage: (page: number) => void;
}

/** Navegación compacta para datos recientes, que siempre llegan acotados por la API. */
export function DrawerPager({ page, pages, total, onPage }: DrawerPagerProps) {
    if (total === 0) return null;

    const from = (page - 1) * DRAWER_PAGE_SIZE + 1;
    const to = Math.min(total, page * DRAWER_PAGE_SIZE);

    return (
        <div className="drawer-pager">
            <span>{from}–{to} de {total}</span>
            {pages > 1 && (
                <div className="drawer-pager__buttons">
                    <button className="btn btn--secondary btn--sm" disabled={page === 1} onClick={() => onPage(page - 1)}>
                        Anterior
                    </button>
                    <button className="btn btn--secondary btn--sm" disabled={page === pages} onClick={() => onPage(page + 1)}>
                        Siguiente
                    </button>
                </div>
            )}
        </div>
    );
}
