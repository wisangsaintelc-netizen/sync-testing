import { useEffect, useState } from 'react';

type IntervalUnit = 'seconds' | 'minutes' | 'hours';

const MULTIPLIER: Record<IntervalUnit, number> = {
    seconds: 1,
    minutes: 60,
    hours: 3600,
};

function parts(seconds: number): { value: number; unit: IntervalUnit } {
    if (seconds > 0 && seconds % 3600 === 0) return { value: seconds / 3600, unit: 'hours' };
    if (seconds > 0 && seconds % 60 === 0) return { value: seconds / 60, unit: 'minutes' };

    return { value: seconds, unit: 'seconds' };
}

export function IntervalInput({ seconds, onChange }: { seconds: number; onChange: (seconds: number) => void }) {
    const [state, setState] = useState(() => parts(seconds));

    useEffect(() => setState(parts(seconds)), [seconds]);

    const update = (value: number, unit: IntervalUnit) => {
        setState({ value, unit });
        onChange(Math.max(60, Math.round(value * MULTIPLIER[unit])));
    };

    return (
        <div className="interval-input">
            <input
                className="assignment-control interval-input__value mono"
                type="number"
                min={state.unit === 'seconds' ? 60 : 1}
                value={state.value}
                onChange={(event) => update(Number(event.target.value), state.unit)}
                aria-label="Valor del intervalo"
            />
            <select
                className="assignment-control interval-input__unit"
                value={state.unit}
                onChange={(event) => {
                    const unit = event.target.value as IntervalUnit;
                    update(Math.max(1, Math.round((state.value * MULTIPLIER[state.unit]) / MULTIPLIER[unit])), unit);
                }}
                aria-label="Unidad del intervalo"
            >
                <option value="seconds">segundos</option>
                <option value="minutes">minutos</option>
                <option value="hours">horas</option>
            </select>
        </div>
    );
}
