<?php

// Configurações iniciais
ini_set('display_errors', 1);
error_reporting(E_ALL);

// Autoload do Composer
require_once __DIR__ . '/../vendor/autoload.php';

// Carregar variáveis de ambiente
use Dotenv\Dotenv;

if (file_exists(__DIR__ . '/../.env')) {
    $dotenv = Dotenv::createImmutable(__DIR__ . '/..');
    $dotenv->load();
}

// Configurações de timezone
date_default_timezone_set('America/Sao_Paulo');

// Configurações de sessão
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

// Headers de segurança
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('X-XSS-Protection: 1; mode=block');

// Funções auxiliares globais
function env($key, $default = null) {
    return $_ENV[$key] ?? $default;
}

function slugify($text) {
    // Converter para minúsculas
    $text = strtolower($text);
    
    // Remover acentos
    $text = iconv('UTF-8', 'ASCII//TRANSLIT', $text);
    
    // Remover caracteres especiais
    $text = preg_replace('/[^a-z0-9\s-]/', '', $text);
    
    // Substituir espaços e múltiplos hífens por um hífen
    $text = preg_replace('/[\s-]+/', '-', $text);
    
    // Remover hífens do início e fim
    return trim($text, '-');
}

function formatCurrency($amount) {
    return 'R$ ' . number_format($amount, 2, ',', '.');
}

function formatDate($date, $format = 'd/m/Y H:i') {
    return date($format, strtotime($date));
}

function escape($string) {
    return htmlspecialchars($string, ENT_QUOTES, 'UTF-8');
}

function redirect($url) {
    header("Location: $url");
    exit;
}

function jsonResponse($data, $statusCode = 200) {
    http_response_code($statusCode);
    header('Content-Type: application/json');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}