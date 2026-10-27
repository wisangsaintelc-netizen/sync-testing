<?php

use Illuminate\Support\Facades\Route;

// SPA React: toda ruta no-API la resuelve el router del frontend.
Route::view('/{any}', 'app')->where('any', '^(?!api).*$');
