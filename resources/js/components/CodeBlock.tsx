/** Bloque navy + texto verde menta para "Configuración activa" y "Payload". */
export function CodeBlock({ children }: { children: string }) {
    return <pre className="codeblock">{children}</pre>;
}
