import { IconSearch } from './icons';

export interface ChipOption {
    value: string;
    label: string;
}

interface FilterBarProps {
    searchValue: string;
    onSearch: (value: string) => void;
    searchPlaceholder?: string;
    chips?: ChipOption[];
    activeChip?: string;
    onChip?: (value: string) => void;
    count?: string;
}

/**
 * Barra de filtros estándar: buscador + chips segmentados (uno activo) + contador.
 * Toda vista de listado la reutiliza — no inventar layouts de filtros distintos.
 */
export function FilterBar({ searchValue, onSearch, searchPlaceholder, chips, activeChip, onChip, count }: FilterBarProps) {
    return (
        <div className="filterbar">
            <label className="filterbar__search">
                <IconSearch size={14} />
                <input
                    value={searchValue}
                    onChange={(e) => onSearch(e.target.value)}
                    placeholder={searchPlaceholder ?? 'Buscar…'}
                />
            </label>
            {chips?.map((c) => (
                <button
                    key={c.value}
                    className={`chip${activeChip === c.value ? ' chip--active' : ''}`}
                    onClick={() => onChip?.(c.value)}
                >
                    {c.label}
                </button>
            ))}
            {count && <div className="filterbar__count">{count}</div>}
        </div>
    );
}
