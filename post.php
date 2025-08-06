<?php
require_once 'config/bootstrap.php';

use App\Models\Post;
use App\Models\Category;

if (!isset($_GET['slug'])) {
    redirect('index.php');
}

$postModel = new Post();
$categoryModel = new Category();

$post = $postModel->getBySlug($_GET['slug']);

if (!$post) {
    http_response_code(404);
    include '404.php';
    exit;
}

// Posts relacionados
$relatedPosts = [];
if ($post['category_id']) {
    $relatedPosts = $postModel->getByCategory($post['category_slug'], 4);
    // Remove o post atual da lista
    $relatedPosts = array_filter($relatedPosts, function($relatedPost) use ($post) {
        return $relatedPost['id'] !== $post['id'];
    });
    $relatedPosts = array_slice($relatedPosts, 0, 3);
}

$recentPosts = $postModel->getRecent(5);

function parseMarkdown($text) {
    // Converter markdown básico para HTML
    $text = preg_replace('/^## (.+)$/m', '<h2>$1</h2>', $text);
    $text = preg_replace('/^### (.+)$/m', '<h3>$1</h3>', $text);
    $text = preg_replace('/\*\*(.+?)\*\*/', '<strong>$1</strong>', $text);
    $text = preg_replace('/\*(.+?)\*/', '<em>$1</em>', $text);
    $text = preg_replace('/^\- (.+)$/m', '<li>$1</li>', $text);
    $text = preg_replace('/(<li>.*<\/li>)/s', '<ul>$1</ul>', $text);
    $text = nl2br($text);
    return $text;
}

function estimateReadingTime($content) {
    $wordCount = str_word_count(strip_tags($content));
    $minutes = max(1, round($wordCount / 200)); // 200 palavras por minuto
    return $minutes;
}

function timeAgo($datetime) {
    $time = time() - strtotime($datetime);
    
    if ($time < 60) return 'há poucos segundos';
    if ($time < 3600) return 'há ' . floor($time/60) . ' minutos';
    if ($time < 86400) return 'há ' . floor($time/3600) . ' horas';
    if ($time < 2592000) return 'há ' . floor($time/86400) . ' dias';
    if ($time < 31536000) return 'há ' . floor($time/2592000) . ' meses';
    
    return 'há ' . floor($time/31536000) . ' anos';
}

$readingTime = estimateReadingTime($post['content']);
$postContent = parseMarkdown($post['content']);
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= htmlspecialchars($post['title']) ?> - Blog Milhas Aéreas</title>
    <meta name="description" content="<?= htmlspecialchars($post['excerpt']) ?>">
    
    <!-- Open Graph Meta Tags -->
    <meta property="og:title" content="<?= htmlspecialchars($post['title']) ?>">
    <meta property="og:description" content="<?= htmlspecialchars($post['excerpt']) ?>">
    <meta property="og:image" content="<?= htmlspecialchars($post['featured_image']) ?>">
    <meta property="og:url" content="<?= env('SITE_URL', 'http://localhost') ?>/post.php?slug=<?= htmlspecialchars($post['slug']) ?>">
    <meta property="og:type" content="article">
    
    <!-- Twitter Card Meta Tags -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="<?= htmlspecialchars($post['title']) ?>">
    <meta name="twitter:description" content="<?= htmlspecialchars($post['excerpt']) ?>">
    <meta name="twitter:image" content="<?= htmlspecialchars($post['featured_image']) ?>">
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Custom CSS -->
    <link rel="stylesheet" href="assets/css/style.css">

    <!-- Structured Data -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": "<?= htmlspecialchars($post['title']) ?>",
        "description": "<?= htmlspecialchars($post['excerpt']) ?>",
        "image": "<?= htmlspecialchars($post['featured_image']) ?>",
        "datePublished": "<?= $post['published_at'] ?>",
        "dateModified": "<?= $post['updated_at'] ?>",
        "author": {
            "@type": "Organization",
            "name": "Blog Milhas Aéreas"
        },
        "publisher": {
            "@type": "Organization",
            "name": "Blog Milhas Aéreas",
            "logo": {
                "@type": "ImageObject",
                "url": "<?= env('SITE_URL', 'http://localhost') ?>/assets/img/logo.png"
            }
        }
    }
    </script>
</head>
<body>
    <!-- Header -->
    <header class="bg-primary text-white">
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container">
                <a class="navbar-brand fw-bold" href="index.php">
                    <i class="fas fa-plane me-2"></i>Blog Milhas Aéreas
                </a>
                
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                    <span class="navbar-toggler-icon"></span>
                </button>
                
                <div class="collapse navbar-collapse" id="navbarNav">
                    <ul class="navbar-nav me-auto">
                        <li class="nav-item">
                            <a class="nav-link" href="index.php">Início</a>
                        </li>
                        <?php 
                        $categories = $categoryModel->getWithPostCount();
                        foreach ($categories as $category): 
                        ?>
                        <li class="nav-item">
                            <a class="nav-link" href="index.php?category=<?= htmlspecialchars($category['slug']) ?>">
                                <?= htmlspecialchars($category['name']) ?>
                            </a>
                        </li>
                        <?php endforeach; ?>
                    </ul>
                    
                    <!-- Search Form -->
                    <form class="d-flex" method="GET" action="index.php">
                        <input class="form-control me-2" type="search" name="search" placeholder="Buscar posts...">
                        <button class="btn btn-outline-light" type="submit">
                            <i class="fas fa-search"></i>
                        </button>
                    </form>
                </div>
            </div>
        </nav>
    </header>

    <!-- Breadcrumb -->
    <nav class="bg-light border-bottom">
        <div class="container">
            <ol class="breadcrumb py-3 mb-0">
                <li class="breadcrumb-item"><a href="index.php">Início</a></li>
                <?php if ($post['category_name']): ?>
                <li class="breadcrumb-item">
                    <a href="index.php?category=<?= htmlspecialchars($post['category_slug']) ?>">
                        <?= htmlspecialchars($post['category_name']) ?>
                    </a>
                </li>
                <?php endif; ?>
                <li class="breadcrumb-item active"><?= htmlspecialchars($post['title']) ?></li>
            </ol>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="py-5">
        <div class="container">
            <div class="row">
                <!-- Post Content -->
                <div class="col-lg-8">
                    <article class="post-detail">
                        <!-- Post Header -->
                        <header class="post-header mb-4">
                            <?php if ($post['category_name']): ?>
                            <div class="mb-3">
                                <span class="badge fs-6 px-3 py-2" style="background-color: <?= $post['category_color'] ?>">
                                    <?= htmlspecialchars($post['category_name']) ?>
                                </span>
                            </div>
                            <?php endif; ?>
                            
                            <h1 class="display-6 fw-bold mb-4"><?= htmlspecialchars($post['title']) ?></h1>
                            
                            <div class="post-meta d-flex flex-wrap align-items-center gap-4 text-muted mb-4">
                                <span>
                                    <i class="fas fa-calendar-alt me-2"></i>
                                    <?= formatDate($post['published_at'], 'd/m/Y') ?>
                                </span>
                                <span>
                                    <i class="fas fa-clock me-2"></i>
                                    <?= $readingTime ?> min de leitura
                                </span>
                                <span>
                                    <i class="fas fa-eye me-2"></i>
                                    <?= number_format($post['views']) ?> visualizações
                                </span>
                                <?php if ($post['is_ai_generated']): ?>
                                <span class="badge bg-info" title="Conteúdo gerado por IA">
                                    <i class="fas fa-robot me-1"></i>Gerado por IA
                                </span>
                                <?php endif; ?>
                            </div>

                            <?php if ($post['excerpt']): ?>
                            <div class="post-excerpt bg-light p-4 rounded mb-4">
                                <p class="lead mb-0"><?= htmlspecialchars($post['excerpt']) ?></p>
                            </div>
                            <?php endif; ?>
                        </header>

                        <!-- Featured Image -->
                        <?php if ($post['featured_image']): ?>
                        <div class="post-image mb-4">
                            <img src="<?= htmlspecialchars($post['featured_image']) ?>" 
                                 class="img-fluid rounded shadow-sm" 
                                 alt="<?= htmlspecialchars($post['title']) ?>">
                        </div>
                        <?php endif; ?>

                        <!-- Post Content -->
                        <div class="post-content">
                            <?= $postContent ?>
                        </div>

                        <!-- Post Tags -->
                        <?php if (!empty($post['tags'])): ?>
                        <div class="post-tags mt-5">
                            <h6 class="fw-bold mb-3">Tags:</h6>
                            <div class="d-flex flex-wrap gap-2">
                                <?php foreach ($post['tags'] as $tag): ?>
                                <span class="badge bg-outline-primary">
                                    <i class="fas fa-tag me-1"></i><?= htmlspecialchars($tag['name']) ?>
                                </span>
                                <?php endforeach; ?>
                            </div>
                        </div>
                        <?php endif; ?>

                        <!-- Share Buttons -->
                        <div class="post-share mt-5 pt-4 border-top">
                            <h6 class="fw-bold mb-3">Compartilhar:</h6>
                            <div class="d-flex gap-2">
                                <a href="https://www.facebook.com/sharer/sharer.php?u=<?= urlencode(env('SITE_URL', 'http://localhost') . '/post.php?slug=' . $post['slug']) ?>" 
                                   target="_blank" class="btn btn-outline-primary btn-sm">
                                    <i class="fab fa-facebook-f me-1"></i>Facebook
                                </a>
                                <a href="https://twitter.com/intent/tweet?url=<?= urlencode(env('SITE_URL', 'http://localhost') . '/post.php?slug=' . $post['slug']) ?>&text=<?= urlencode($post['title']) ?>" 
                                   target="_blank" class="btn btn-outline-info btn-sm">
                                    <i class="fab fa-twitter me-1"></i>Twitter
                                </a>
                                <a href="https://www.linkedin.com/sharing/share-offsite/?url=<?= urlencode(env('SITE_URL', 'http://localhost') . '/post.php?slug=' . $post['slug']) ?>" 
                                   target="_blank" class="btn btn-outline-primary btn-sm">
                                    <i class="fab fa-linkedin me-1"></i>LinkedIn
                                </a>
                                <a href="https://api.whatsapp.com/send?text=<?= urlencode($post['title'] . ' - ' . env('SITE_URL', 'http://localhost') . '/post.php?slug=' . $post['slug']) ?>" 
                                   target="_blank" class="btn btn-outline-success btn-sm">
                                    <i class="fab fa-whatsapp me-1"></i>WhatsApp
                                </a>
                            </div>
                        </div>
                    </article>

                    <!-- Related Posts -->
                    <?php if (!empty($relatedPosts)): ?>
                    <section class="related-posts mt-5 pt-5 border-top">
                        <h3 class="h4 fw-bold mb-4">Posts Relacionados</h3>
                        <div class="row">
                            <?php foreach ($relatedPosts as $relatedPost): ?>
                            <div class="col-md-4 mb-4">
                                <div class="card h-100 shadow-sm">
                                    <?php if ($relatedPost['featured_image']): ?>
                                    <img src="<?= htmlspecialchars($relatedPost['featured_image']) ?>" 
                                         class="card-img-top" style="height: 150px; object-fit: cover;">
                                    <?php endif; ?>
                                    <div class="card-body">
                                        <h6 class="card-title">
                                            <a href="post.php?slug=<?= htmlspecialchars($relatedPost['slug']) ?>" 
                                               class="text-decoration-none text-dark">
                                                <?= htmlspecialchars($relatedPost['title']) ?>
                                            </a>
                                        </h6>
                                        <small class="text-muted">
                                            <?= timeAgo($relatedPost['published_at']) ?>
                                        </small>
                                    </div>
                                </div>
                            </div>
                            <?php endforeach; ?>
                        </div>
                    </section>
                    <?php endif; ?>
                </div>

                <!-- Sidebar -->
                <div class="col-lg-4">
                    <div class="sidebar">
                        <!-- Recent Posts -->
                        <div class="card mb-4">
                            <div class="card-header bg-primary text-white">
                                <h5 class="mb-0"><i class="fas fa-clock me-2"></i>Posts Recentes</h5>
                            </div>
                            <div class="card-body">
                                <?php foreach ($recentPosts as $recentPost): ?>
                                <div class="mb-3">
                                    <h6 class="mb-1">
                                        <a href="post.php?slug=<?= htmlspecialchars($recentPost['slug']) ?>" 
                                           class="text-decoration-none">
                                            <?= htmlspecialchars(substr($recentPost['title'], 0, 60)) ?><?= strlen($recentPost['title']) > 60 ? '...' : '' ?>
                                        </a>
                                    </h6>
                                    <small class="text-muted">
                                        <?= timeAgo($recentPost['published_at']) ?>
                                        <?php if ($recentPost['category_name']): ?>
                                        • <?= htmlspecialchars($recentPost['category_name']) ?>
                                        <?php endif; ?>
                                    </small>
                                </div>
                                <?php endforeach; ?>
                            </div>
                        </div>

                        <!-- Categories -->
                        <div class="card mb-4">
                            <div class="card-header bg-info text-white">
                                <h5 class="mb-0"><i class="fas fa-tags me-2"></i>Categorias</h5>
                            </div>
                            <div class="card-body">
                                <div class="d-flex flex-wrap gap-2">
                                    <?php foreach ($categories as $category): ?>
                                    <a href="index.php?category=<?= htmlspecialchars($category['slug']) ?>" 
                                       class="btn btn-outline-secondary btn-sm">
                                        <?= htmlspecialchars($category['name']) ?>
                                        <span class="badge bg-secondary ms-1"><?= $category['post_count'] ?></span>
                                    </a>
                                    <?php endforeach; ?>
                                </div>
                            </div>
                        </div>

                        <!-- Newsletter -->
                        <div class="card mb-4 bg-light">
                            <div class="card-body text-center">
                                <h5 class="card-title"><i class="fas fa-envelope me-2"></i>Newsletter</h5>
                                <p class="card-text">Receba as melhores dicas sobre milhas aéreas!</p>
                                <form>
                                    <div class="input-group">
                                        <input type="email" class="form-control" placeholder="Seu e-mail">
                                        <button class="btn btn-primary" type="submit">
                                            <i class="fas fa-paper-plane"></i>
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="bg-dark text-white py-5">
        <div class="container">
            <div class="row">
                <div class="col-lg-6">
                    <h5><i class="fas fa-plane me-2"></i>Blog Milhas Aéreas</h5>
                    <p class="text-muted">Seu guia completo para o mundo das milhas aéreas. Dicas, estratégias e promoções para você viajar mais gastando menos.</p>
                </div>
                <div class="col-lg-6 text-lg-end">
                    <p class="mb-0 text-muted">
                        &copy; <?= date('Y') ?> Blog Milhas Aéreas. Desenvolvido por 
                        <a href="https://enigmasolutions.com.br" class="text-white">Enigma Solutions</a>
                    </p>
                </div>
            </div>
        </div>
    </footer>

    <!-- Scroll to Top Button -->
    <button class="scroll-top" onclick="scrollToTop()">
        <i class="fas fa-arrow-up"></i>
    </button>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- Custom JS -->
    <script>
        // Scroll to top functionality
        window.addEventListener('scroll', () => {
            const scrollTop = document.querySelector('.scroll-top');
            if (window.pageYOffset > 300) {
                scrollTop.classList.add('show');
            } else {
                scrollTop.classList.remove('show');
            }
        });

        function scrollToTop() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        // Reading progress bar
        const progressBar = document.createElement('div');
        progressBar.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 0%;
            height: 3px;
            background: var(--primary-color);
            z-index: 9999;
            transition: width 0.1s;
        `;
        document.body.appendChild(progressBar);

        window.addEventListener('scroll', () => {
            const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
            const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
            const scrolled = (winScroll / height) * 100;
            progressBar.style.width = scrolled + '%';
        });
    </script>
</body>
</html>