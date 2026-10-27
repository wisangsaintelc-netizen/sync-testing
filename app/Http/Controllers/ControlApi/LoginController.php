<?php

namespace App\Http\Controllers\ControlApi;

use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\LoginRequest;
use App\Models\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Hash;
use Symfony\Component\HttpFoundation\Response;

class LoginController extends Controller
{
    public function __invoke(LoginRequest $request): JsonResponse
    {
        $credentials = $request->validated();
        $user = User::where('email', $credentials['email'])->first();

        if (! $user || ! Hash::check($credentials['password'], $user->password)) {
            return response()->json([
                'error' => ['code' => 'AUTHENTICATION_FAILED', 'message' => 'Credenciales inválidas.'],
            ], Response::HTTP_UNAUTHORIZED);
        }

        $user->tokens()->where('name', 'control-api')->delete();
        $token = $user->createToken(
            name: 'control-api',
            abilities: ['control-api'],
            expiresAt: now()->addHours(8),
        )->plainTextToken;

        return response()->json([
            'token' => $token,
            'user' => ['name' => $user->name, 'email' => $user->email, 'role' => 'operator'],
        ]);
    }
}
