import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Estado estándar de una vista de listado: búsqueda (inicializada desde
 * ?search= de la URL, que alimenta el buscador global de la topbar),
 * chip activo y página.
 */
export function useListView(defaultChip = '') {
    const [searchParams] = useSearchParams();
    const urlSearch = searchParams.get('search') ?? '';
    const [search, setSearch] = useState(urlSearch);
    const [chip, setChip] = useState(defaultChip);
    const [page, setPage] = useState(1);

    // El buscador global navega con ?search=; sincronizar al cambiar.
    useEffect(() => {
        setSearch(urlSearch);
        setPage(1);
    }, [urlSearch]);

    const onSearch = (v: string) => {
        setSearch(v);
        setPage(1);
    };

    const onChip = (v: string) => {
        setChip(v);
        setPage(1);
    };

    return { search, onSearch, chip, onChip, page, setPage };
}
