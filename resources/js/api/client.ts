/**
 * Cliente HTTP único: baseURL /api/v1, bearer, errores {error:{code,message}}.
 * Las vistas nunca llaman fetch directamente — usan api/endpoints.ts.
 */

const BASE = '/api/v1';
const TOKEN_KEY = 'bapps_sync_token';

export function getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
    localStorage.removeItem(TOKEN_KEY);
}

/** Error de API con código de dominio y status HTTP. */
export class ApiError extends Error {
    constructor(
        public status: number,
        public code: string,
        message: string,
    ) {
        super(message);
        this.name = 'ApiError';
    }
}

interface RequestOptions {
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    body?: unknown;
    params?: Record<string, string | number | undefined>;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { method = 'GET', body, params } = options;

    let url = BASE + path;
    if (params) {
        const qs = new URLSearchParams();
        for (const [k, v] of Object.entries(params)) {
            if (v !== undefined && v !== '') qs.set(k, String(v));
        }
        const s = qs.toString();
        if (s) url += `?${s}`;
    }

    const headers: Record<string, string> = { Accept: 'application/json' };
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';

    let res: Response;
    try {
        res = await fetch(url, {
            method,
            headers,
            body: body !== undefined ? JSON.stringify(body) : undefined,
        });
    } catch {
        throw new ApiError(0, 'NETWORK_ERROR', 'No se pudo contactar al servidor.');
    }

    if (res.status === 401) {
        clearToken();
        // El guard de rutas detecta la falta de token y redirige a /login.
        window.dispatchEvent(new CustomEvent('bapps:unauthorized'));
    }

    if (!res.ok) {
        let code = `HTTP_${res.status}`;
        let message = res.statusText;
        try {
            const data = await res.json();
            if (data?.error) {
                code = data.error.code ?? code;
                message = data.error.message ?? message;
            }
        } catch {
            /* cuerpo no-JSON: se mantienen los defaults */
        }
        throw new ApiError(res.status, code, message);
    }

    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
}
