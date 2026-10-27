import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { login } from '@/api/endpoints';
import { setToken, ApiError } from '@/api/client';
import { IconRuns } from '@/components/icons';

export function Login() {
    const navigate = useNavigate();
    const location = useLocation();
    const [email, setEmail] = useState('operator@bapps.test');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
            const res = await login(email, password);
            setToken(res.token);
            const from = (location.state as { from?: string } | null)?.from ?? '/';
            navigate(from, { replace: true });
        } catch (err) {
            setError(err instanceof ApiError ? err.message : 'No se pudo iniciar sesión.');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="login-page">
            <form className="login-card" onSubmit={submit}>
                <div className="login-brand">
                    <div className="sidebar__logo">
                        <IconRuns size={18} />
                    </div>
                    <div>
                        <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-strong)' }}>BAPPS Sync</div>
                        <div className="kicker">Centro de operaciones</div>
                    </div>
                </div>

                {error && <div className="login-error">{error}</div>}

                <div className="field">
                    <label className="field__label">Email</label>
                    <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
                </div>
                <div className="field">
                    <label className="field__label">Contraseña</label>
                    <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        autoComplete="current-password"
                        placeholder="Contraseña del operador"
                        required
                    />
                </div>

                <button className="btn btn--primary" disabled={busy} type="submit">
                    {busy ? 'Entrando…' : 'Entrar'}
                </button>
                <div style={{ fontSize: 11, color: 'var(--text-3)', textAlign: 'center' }}>
                    Usa las credenciales del operador configurado en el Centro BAPPS.
                </div>
            </form>
        </div>
    );
}
