<?php

namespace App\Services;

use GuzzleHttp\Client;
use GuzzleHttp\Exception\GuzzleException;
use App\Models\AILog;

class AIService
{
    private $client;
    private $apiKey;
    private $model;
    private $aiLog;

    public function __construct()
    {
        $this->client = new Client();
        $this->apiKey = $_ENV['OPENAI_API_KEY'] ?? '';
        $this->model = $_ENV['AI_MODEL'] ?? 'gpt-3.5-turbo';
        $this->aiLog = new AILog();
    }

    public function generatePost($topic, $category = null): array
    {
        $prompt = $this->buildPrompt($topic, $category);
        
        try {
            $response = $this->callOpenAI($prompt);
            
            if ($response && isset($response['choices'][0]['message']['content'])) {
                $content = $response['choices'][0]['message']['content'];
                $parsedContent = $this->parseGeneratedContent($content);
                
                // Log da requisição
                $this->aiLog->create([
                    'prompt' => $prompt,
                    'response' => $content,
                    'model' => $this->model,
                    'tokens_used' => $response['usage']['total_tokens'] ?? 0,
                    'status' => 'success'
                ]);
                
                return $parsedContent;
            }
        } catch (\Exception $e) {
            // Log do erro
            $this->aiLog->create([
                'prompt' => $prompt,
                'response' => null,
                'model' => $this->model,
                'status' => 'error',
                'error_message' => $e->getMessage()
            ]);
            
            throw new \Exception('Erro ao gerar conteúdo: ' . $e->getMessage());
        }
        
        throw new \Exception('Não foi possível gerar o conteúdo');
    }

    private function buildPrompt($topic, $category): string
    {
        $categoryContext = '';
        if ($category) {
            $categoryContext = "na categoria '{$category}' ";
        }

        return "Escreva um artigo completo para um blog sobre milhas aéreas {$categoryContext}sobre o seguinte tópico: '{$topic}'.

O artigo deve:
1. Ter um título atrativo e otimizado para SEO
2. Incluir um resumo/excerpt de 2-3 linhas
3. Conter entre 800-1200 palavras
4. Ser informativo e útil para pessoas interessadas em milhas aéreas
5. Incluir dicas práticas e exemplos reais
6. Ter uma linguagem acessível mas profissional
7. Mencionar programas de fidelidade brasileiros (Azul, TAM, Gol) quando relevante
8. Incluir pelo menos 3 subtítulos (usar ## para markdown)

Formate a resposta em JSON com a seguinte estrutura:
{
  \"title\": \"Título do artigo\",
  \"excerpt\": \"Resumo do artigo\",
  \"content\": \"Conteúdo completo em markdown\",
  \"suggested_tags\": [\"tag1\", \"tag2\", \"tag3\"]
}

Importante: O conteúdo deve ser 100% original, útil e focado no mercado brasileiro de milhas aéreas.";
    }

    private function callOpenAI($prompt): ?array
    {
        if (empty($this->apiKey)) {
            throw new \Exception('API Key da OpenAI não configurada');
        }

        try {
            $response = $this->client->post('https://api.openai.com/v1/chat/completions', [
                'headers' => [
                    'Authorization' => 'Bearer ' . $this->apiKey,
                    'Content-Type' => 'application/json',
                ],
                'json' => [
                    'model' => $this->model,
                    'messages' => [
                        [
                            'role' => 'system',
                            'content' => 'Você é um especialista em milhas aéreas e programas de fidelidade no Brasil. Escreva conteúdo informativo, prático e atualizado sobre o tema.'
                        ],
                        [
                            'role' => 'user',
                            'content' => $prompt
                        ]
                    ],
                    'max_tokens' => 2000,
                    'temperature' => 0.7,
                ]
            ]);

            return json_decode($response->getBody()->getContents(), true);
        } catch (GuzzleException $e) {
            throw new \Exception('Erro na comunicação com a API: ' . $e->getMessage());
        }
    }

    private function parseGeneratedContent($content): array
    {
        // Tentar fazer parse do JSON
        $decoded = json_decode($content, true);
        
        if (json_last_error() === JSON_ERROR_NONE && isset($decoded['title']) && isset($decoded['content'])) {
            return [
                'title' => $decoded['title'],
                'excerpt' => $decoded['excerpt'] ?? '',
                'content' => $decoded['content'],
                'suggested_tags' => $decoded['suggested_tags'] ?? []
            ];
        }
        
        // Se não for JSON válido, tentar extrair o conteúdo manualmente
        $lines = explode("\n", $content);
        $title = '';
        $excerpt = '';
        $mainContent = [];
        $inContent = false;
        
        foreach ($lines as $line) {
            $line = trim($line);
            
            if (empty($title) && !empty($line)) {
                $title = $line;
                continue;
            }
            
            if (empty($excerpt) && !empty($line) && $line !== $title) {
                $excerpt = $line;
                $inContent = true;
                continue;
            }
            
            if ($inContent) {
                $mainContent[] = $line;
            }
        }
        
        return [
            'title' => $title ?: 'Artigo sobre Milhas Aéreas',
            'excerpt' => $excerpt ?: 'Conteúdo informativo sobre milhas aéreas.',
            'content' => implode("\n", $mainContent) ?: $content,
            'suggested_tags' => ['milhas', 'viagem', 'dicas']
        ];
    }

    public function generateTopics($category = null, $count = 5): array
    {
        $categoryContext = $category ? "na categoria '{$category}'" : '';
        
        $prompt = "Gere {$count} ideias de tópicos para artigos de blog sobre milhas aéreas {$categoryContext}.
        
Os tópicos devem ser:
- Específicos e práticos
- Relevantes para o mercado brasileiro
- Atuais e interessantes
- Focados em resolver problemas reais dos leitores

Retorne apenas uma lista simples, um tópico por linha, sem numeração ou marcadores.";

        try {
            $response = $this->callOpenAI($prompt);
            
            if ($response && isset($response['choices'][0]['message']['content'])) {
                $content = trim($response['choices'][0]['message']['content']);
                $topics = array_filter(array_map('trim', explode("\n", $content)));
                
                return array_slice($topics, 0, $count);
            }
        } catch (\Exception $e) {
            // Em caso de erro, retornar tópicos padrão
            return $this->getDefaultTopics($category, $count);
        }
        
        return $this->getDefaultTopics($category, $count);
    }

    private function getDefaultTopics($category, $count): array
    {
        $allTopics = [
            'Como acumular milhas rapidamente com cartão de crédito',
            'Melhores cartões para acumular milhas em 2024',
            'Guia completo do programa Azul Fidelidade',
            'Como transferir milhas entre programas de fidelidade',
            'Dicas para viajar de primeira classe usando milhas',
            'Promoções de milhas que você não pode perder',
            'Como usar milhas para upgrade de classe',
            'Programas de fidelidade internacionais para brasileiros',
            'Estratégias para maximizar o acúmulo de milhas',
            'Como resgatar passagens com melhor custo-benefício',
            'Erros comuns ao usar milhas aéreas',
            'Guia de transferências de milhas do Santander',
            'Como funciona o programa Smiles da Gol',
            'Melhores destinos para usar milhas',
            'Planejamento de viagem usando apenas milhas'
        ];
        
        shuffle($allTopics);
        return array_slice($allTopics, 0, $count);
    }

    public function improveContent($content, $improvements): string
    {
        $prompt = "Melhore o seguinte conteúdo sobre milhas aéreas aplicando as seguintes melhorias: " . implode(', ', $improvements) . "

Conteúdo original:
{$content}

Retorne o conteúdo melhorado mantendo o formato markdown e a estrutura original.";

        try {
            $response = $this->callOpenAI($prompt);
            
            if ($response && isset($response['choices'][0]['message']['content'])) {
                return trim($response['choices'][0]['message']['content']);
            }
        } catch (\Exception $e) {
            throw new \Exception('Erro ao melhorar conteúdo: ' . $e->getMessage());
        }
        
        return $content; // Retorna o conteúdo original se houver erro
    }

    public function generateMetaDescription($title, $content, $maxLength = 160): string
    {
        $prompt = "Crie uma meta description otimizada para SEO com até {$maxLength} caracteres para o seguinte artigo sobre milhas aéreas:

Título: {$title}
Primeiros parágrafos: " . substr(strip_tags($content), 0, 300) . "

A meta description deve:
- Ser atrativa e persuasiva
- Incluir palavras-chave relevantes
- Ter chamada para ação
- Estar dentro do limite de caracteres";

        try {
            $response = $this->callOpenAI($prompt);
            
            if ($response && isset($response['choices'][0]['message']['content'])) {
                $metaDescription = trim($response['choices'][0]['message']['content']);
                
                // Garantir que não exceda o limite
                if (strlen($metaDescription) > $maxLength) {
                    $metaDescription = substr($metaDescription, 0, $maxLength - 3) . '...';
                }
                
                return $metaDescription;
            }
        } catch (\Exception $e) {
            // Fallback: criar meta description simples
            $simpleDescription = substr(strip_tags($content), 0, $maxLength - 3) . '...';
            return $simpleDescription;
        }
        
        return '';
    }
}