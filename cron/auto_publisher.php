<?php
require_once __DIR__ . '/../config/bootstrap.php';

use App\Models\Post;
use App\Models\Category;
use App\Models\AILog;
use App\Services\AIService;

// Log de execução
echo "[" . date('Y-m-d H:i:s') . "] Iniciando processo de publicação automática...\n";

try {
    $postModel = new Post();
    $categoryModel = new Category();
    $aiService = new AIService();
    
    // Verificar se a publicação automática está habilitada
    if (!env('AUTO_POST_ENABLED', true)) {
        echo "Publicação automática desabilitada.\n";
        exit;
    }
    
    // Verificar limite de posts por dia
    $maxPostsPerDay = env('MAX_POSTS_PER_DAY', 3);
    $today = date('Y-m-d');
    
    $todayPosts = $postModel->getAll('published', 100);
    $todayPostsCount = 0;
    
    foreach ($todayPosts as $post) {
        if (date('Y-m-d', strtotime($post['published_at'])) === $today && $post['is_ai_generated']) {
            $todayPostsCount++;
        }
    }
    
    if ($todayPostsCount >= $maxPostsPerDay) {
        echo "Limite diário de posts atingido ($todayPostsCount/$maxPostsPerDay).\n";
        exit;
    }
    
    // Publicar posts agendados
    $scheduledPosts = $postModel->getScheduledPosts();
    foreach ($scheduledPosts as $scheduledPost) {
        $postModel->publishScheduledPost($scheduledPost['id']);
        echo "Post agendado publicado: {$scheduledPost['title']}\n";
    }
    
    // Gerar novos posts com IA
    $categories = $categoryModel->getAll();
    $selectedCategory = $categories[array_rand($categories)];
    
    echo "Gerando novo post para categoria: {$selectedCategory['name']}\n";
    
    // Gerar tópicos
    $topics = $aiService->generateTopics($selectedCategory['name'], 3);
    $selectedTopic = $topics[array_rand($topics)];
    
    echo "Tópico selecionado: $selectedTopic\n";
    
    // Gerar conteúdo
    $generatedContent = $aiService->generatePost($selectedTopic, $selectedCategory['name']);
    
    // Criar slug
    $slug = slugify($generatedContent['title']);
    
    // Verificar se slug já existe
    $existingPost = $postModel->getBySlug($slug);
    $counter = 1;
    $originalSlug = $slug;
    
    while ($existingPost) {
        $slug = $originalSlug . '-' . $counter;
        $existingPost = $postModel->getBySlug($slug);
        $counter++;
    }
    
    // Preparar dados do post
    $postData = [
        'title' => $generatedContent['title'],
        'slug' => $slug,
        'excerpt' => $generatedContent['excerpt'],
        'content' => $generatedContent['content'],
        'featured_image' => getRandomImage($selectedTopic),
        'category_id' => $selectedCategory['id'],
        'status' => 'published',
        'is_ai_generated' => true,
        'ai_prompt' => "Tópico: $selectedTopic | Categoria: {$selectedCategory['name']}",
        'published_at' => date('Y-m-d H:i:s')
    ];
    
    // Criar post
    $postId = $postModel->create($postData);
    
    if ($postId) {
        echo "Post criado com sucesso! ID: $postId\n";
        echo "Título: {$generatedContent['title']}\n";
        echo "Slug: $slug\n";
        
        // Adicionar tags se existirem
        if (!empty($generatedContent['suggested_tags'])) {
            $tagModel = new \App\Models\Tag();
            $tagIds = [];
            
            foreach ($generatedContent['suggested_tags'] as $tagName) {
                $tag = $tagModel->getByName($tagName);
                if (!$tag) {
                    $tagId = $tagModel->create([
                        'name' => $tagName,
                        'slug' => slugify($tagName)
                    ]);
                } else {
                    $tagId = $tag['id'];
                }
                $tagIds[] = $tagId;
            }
            
            if (!empty($tagIds)) {
                $postModel->addPostTags($postId, $tagIds);
                echo "Tags adicionadas: " . implode(', ', $generatedContent['suggested_tags']) . "\n";
            }
        }
        
    } else {
        echo "Erro ao criar post.\n";
    }
    
} catch (\Exception $e) {
    echo "Erro: " . $e->getMessage() . "\n";
    
    // Log do erro
    error_log("[Auto Publisher] " . $e->getMessage());
}

echo "[" . date('Y-m-d H:i:s') . "] Processo finalizado.\n\n";

function getRandomImage($topic) {
    // Gerar imagem relacionada ao tópico usando Unsplash
    $keywords = [
        'airplane', 'travel', 'airport', 'vacation', 'flight', 
        'miles', 'credit-card', 'business-class', 'first-class'
    ];
    
    $randomKeyword = $keywords[array_rand($keywords)];
    
    return "https://source.unsplash.com/1200x600/?{$randomKeyword}";
}