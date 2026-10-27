import React from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';

import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-sans/700.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import '@fontsource/ibm-plex-mono/600.css';

import '../styles/tokens.css';
import '../styles/base.css';
import '../styles/layout.css';
import '../styles/components.css';
import '../styles/views.css';

import { queryClient } from './queryClient';
import { router } from './router';
import { ToastProvider } from '@/components/Toast';

async function bootstrap() {
    if (import.meta.env.VITE_USE_MOCKS === 'true') {
        const { worker } = await import('@/mocks/browser');
        await worker.start({
            onUnhandledRequest: 'bypass',
            serviceWorker: { url: '/mockServiceWorker.js' },
        });
    }

    createRoot(document.getElementById('root')!).render(
        <React.StrictMode>
            <QueryClientProvider client={queryClient}>
                <ToastProvider>
                    <RouterProvider router={router} />
                </ToastProvider>
            </QueryClientProvider>
        </React.StrictMode>,
    );
}

void bootstrap();
