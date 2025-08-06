<?php
require_once 'config/bootstrap.php';

use App\Models\Post;
use App\Models\Category;

$postModel = new Post();
$categoryModel = new Category();

// Paginação
$page = isset($_GET['page']) ? (int)$_GET['page'] : 1;
$postsPerPage = 10;
$offset = ($page - 1) * $postsPerPage;

// Busca
$searchQuery = isset($_GET['search']) ? trim($_GET['search']) : '';
$categoryFilter = isset($_GET['category']) ? $_GET['category'] : '';

if ($searchQuery) {
    $posts = $postModel->search($searchQuery, $postsPerPage);
    $totalPosts = count($posts);
} elseif ($categoryFilter) {
    $posts = $postModel->getByCategory($categoryFilter, $postsPerPage, $offset);
    $totalPosts = count($posts); // Simplificado para o exemplo
} else {
    $posts = $postModel->getAll('published', $postsPerPage, $offset);
    $totalPosts = $postModel->getTotalCount('published');
}

$categories = $categoryModel->getWithPostCount();
$recentPosts = $postModel->getRecent(5);
$popularPosts = $postModel->getMostViewed(5);

$totalPages = ceil($totalPosts / $postsPerPage);

function timeAgo($datetime) {
    $time = time() - strtotime($datetime);
    
    if ($time < 60) return 'há poucos segundos';
    if ($time < 3600) return 'há ' . floor($time/60) . ' minutos';
    if ($time < 86400) return 'há ' . floor($time/3600) . ' horas';
    if ($time < 2592000) return 'há ' . floor($time/86400) . ' dias';
    if ($time < 31536000) return 'há ' . floor($time/2592000) . ' meses';
    
    return 'há ' . floor($time/31536000) . ' anos';
}

function truncateText($text, $limit = 150) {
    if (strlen($text) <= $limit) return $text;
    return substr($text, 0, $limit) . '...';
}
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= $searchQuery ? "Resultados para '{$searchQuery}' - " : '' ?>Blog Milhas Aéreas</title>
    <meta name="description" content="O melhor conteúdo sobre milhas aéreas, programas de fidelidade e dicas para viajar mais gastando menos.">
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Custom CSS -->
    <link rel="stylesheet" href="assets/css/style.css">
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
                            <a class="nav-link <?= !$categoryFilter ? 'active' : '' ?>" href="index.php">Início</a>
                        </li>
                        <?php foreach ($categories as $category): ?>
                        <li class="nav-item">
                            <a class="nav-link <?= $categoryFilter === $category['slug'] ? 'active' : '' ?>" 
                               href="index.php?category=<?= htmlspecialchars($category['slug']) ?>">
                                <?= htmlspecialchars($category['name']) ?>
                                <span class="badge bg-light text-dark ms-1"><?= $category['post_count'] ?></span>
                            </a>
                        </li>
                        <?php endforeach; ?>
                    </ul>
                    
                    <!-- Search Form -->
                    <form class="d-flex" method="GET" action="index.php">
                        <input class="form-control me-2" type="search" name="search" 
                               placeholder="Buscar posts..." value="<?= htmlspecialchars($searchQuery) ?>">
                        <button class="btn btn-outline-light" type="submit">
                            <i class="fas fa-search"></i>
                        </button>
                    </form>
                </div>
            </div>
        </nav>
    </header>

    <!-- Hero Section -->
    <?php if (!$searchQuery && !$categoryFilter): ?>
    <section class="hero-section bg-gradient-primary text-white py-5">
        <div class="container">
            <div class="row align-items-center">
                <div class="col-lg-8">
                    <h1 class="display-4 fw-bold mb-3">Maximize suas Milhas Aéreas</h1>
                    <p class="lead mb-4">Descubra as melhores estratégias para acumular milhas, encontrar promoções imperdíveis e viajar mais gastando menos. Conteúdo especializado e sempre atualizado sobre o mundo das milhas aéreas.</p>
                    <div class="d-flex gap-3">
                        <span class="badge bg-light text-dark p-2"><i class="fas fa-credit-card me-1"></i>Cartões de Crédito</span>
                        <span class="badge bg-light text-dark p-2"><i class="fas fa-percentage me-1"></i>Promoções</span>
                        <span class="badge bg-light text-dark p-2"><i class="fas fa-plane me-1"></i>Dicas de Viagem</span>
                    </div>
                </div>
                <div class="col-lg-4 text-center">
                    <i class="fas fa-globe-americas display-1 opacity-75"></i>
                </div>
            </div>
        </div>
    </section>
    <?php endif; ?>

    <!-- Main Content -->
    <main class="py-5">
        <div class="container">
            <div class="row">
                <!-- Posts Column -->
                <div class="col-lg-8">
                    <?php if ($searchQuery): ?>
                    <div class="alert alert-info">
                        <i class="fas fa-search me-2"></i>
                        Resultados para: <strong><?= htmlspecialchars($searchQuery) ?></strong>
                        (<?= count($posts) ?> post<?= count($posts) != 1 ? 's' : '' ?> encontrado<?= count($posts) != 1 ? 's' : '' ?>)
                    </div>
                    <?php endif; ?>

                    <?php if ($categoryFilter): ?>
                    <?php 
                    $currentCategory = $categoryModel->getBySlug($categoryFilter);
                    if ($currentCategory):
                    ?>
                    <div class="category-header mb-4">
                        <h2 class="h3 mb-2">
                            <span class="badge" style="background-color: <?= $currentCategory['color'] ?>">
                                <?= htmlspecialchars($currentCategory['name']) ?>
                            </span>
                        </h2>
                        <?php if ($currentCategory['description']): ?>
                        <p class="text-muted"><?= htmlspecialchars($currentCategory['description']) ?></p>
                        <?php endif; ?>
                    </div>
                    <?php endif; ?>
                    <?php endif; ?>

                    <!-- Posts List -->
                    <div class="posts-list">
                        <?php if (empty($posts)): ?>
                        <div class="text-center py-5">
                            <i class="fas fa-search fa-3x text-muted mb-3"></i>
                            <h3 class="text-muted">Nenhum post encontrado</h3>
                            <p class="text-muted">Tente ajustar sua busca ou navegar pelas categorias.</p>
                            <a href="index.php" class="btn btn-primary">Ver todos os posts</a>
                        </div>
                        <?php else: ?>
                        <?php foreach ($posts as $index => $post): ?>
                        <article class="post-card mb-4 <?= $index === 0 && !$searchQuery && !$categoryFilter ? 'featured' : '' ?>">
                            <div class="card h-100 shadow-sm">
                                <?php if ($post['featured_image']): ?>
                                <img src="<?= htmlspecialchars($post['featured_image']) ?>" 
                                     class="card-img-top" alt="<?= htmlspecialchars($post['title']) ?>"
                                     style="height: <?= $index === 0 && !$searchQuery && !$categoryFilter ? '300px' : '200px' ?>; object-fit: cover;">
                                <?php endif; ?>
                                
                                <div class="card-body">
                                    <div class="d-flex justify-content-between align-items-center mb-2">
                                        <?php if ($post['category_name']): ?>
                                        <span class="badge" style="background-color: <?= $post['category_color'] ?>">
                                            <?= htmlspecialchars($post['category_name']) ?>
                                        </span>
                                        <?php endif; ?>
                                        
                                        <small class="text-muted">
                                            <i class="fas fa-clock me-1"></i>
                                            <?= timeAgo($post['published_at']) ?>
                                        </small>
                                    </div>
                                    
                                    <h3 class="card-title h5">
                                        <a href="post.php?slug=<?= htmlspecialchars($post['slug']) ?>" 
                                           class="text-decoration-none text-dark">
                                            <?= htmlspecialchars($post['title']) ?>
                                        </a>
                                    </h3>
                                    
                                    <?php if ($post['excerpt']): ?>
                                    <p class="card-text text-muted">
                                        <?= truncateText(htmlspecialchars($post['excerpt'])) ?>
                                    </p>
                                    <?php endif; ?>
                                    
                                    <div class="d-flex justify-content-between align-items-center">
                                        <a href="post.php?slug=<?= htmlspecialchars($post['slug']) ?>" 
                                           class="btn btn-primary btn-sm">
                                            Ler mais <i class="fas fa-arrow-right ms-1"></i>
                                        </a>
                                        
                                        <div class="post-stats text-muted small">
                                            <span class="me-3">
                                                <i class="fas fa-eye me-1"></i><?= number_format($post['views']) ?>
                                            </span>
                                            <?php if ($post['is_ai_generated']): ?>
                                            <span class="badge bg-info" title="Conteúdo gerado por IA">
                                                <i class="fas fa-robot"></i> IA
                                            </span>
                                            <?php endif; ?>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </article>
                        <?php endforeach; ?>
                        <?php endif; ?>
                    </div>

                    <!-- Pagination -->
                    <?php if ($totalPages > 1 && !$searchQuery): ?>
                    <nav aria-label="Navegação de páginas">
                        <ul class="pagination justify-content-center">
                            <?php if ($page > 1): ?>
                            <li class="page-item">
                                <a class="page-link" href="?page=<?= $page - 1 ?><?= $categoryFilter ? '&category=' . $categoryFilter : '' ?>">
                                    <i class="fas fa-chevron-left"></i> Anterior
                                </a>
                            </li>
                            <?php endif; ?>
                            
                            <?php for ($i = max(1, $page - 2); $i <= min($totalPages, $page + 2); $i++): ?>
                            <li class="page-item <?= $i === $page ? 'active' : '' ?>">
                                <a class="page-link" href="?page=<?= $i ?><?= $categoryFilter ? '&category=' . $categoryFilter : '' ?>">
                                    <?= $i ?>
                                </a>
                            </li>
                            <?php endfor; ?>
                            
                            <?php if ($page < $totalPages): ?>
                            <li class="page-item">
                                <a class="page-link" href="?page=<?= $page + 1 ?><?= $categoryFilter ? '&category=' . $categoryFilter : '' ?>">
                                    Próxima <i class="fas fa-chevron-right"></i>
                                </a>
                            </li>
                            <?php endif; ?>
                        </ul>
                    </nav>
                    <?php endif; ?>
                </div>

                <!-- Sidebar -->
                <div class="col-lg-4">
                    <div class="sidebar">
                        <!-- Popular Posts -->
                        <div class="card mb-4">
                            <div class="card-header bg-primary text-white">
                                <h5 class="mb-0"><i class="fas fa-fire me-2"></i>Posts Populares</h5>
                            </div>
                            <div class="card-body">
                                <?php foreach ($popularPosts as $popularPost): ?>
                                <div class="d-flex mb-3">
                                    <?php if ($popularPost['featured_image']): ?>
                                    <img src="<?= htmlspecialchars($popularPost['featured_image']) ?>" 
                                         class="me-3 rounded" width="60" height="60" style="object-fit: cover;">
                                    <?php endif; ?>
                                    <div class="flex-grow-1">
                                        <h6 class="mb-1">
                                            <a href="post.php?slug=<?= htmlspecialchars($popularPost['slug']) ?>" 
                                               class="text-decoration-none">
                                                <?= truncateText(htmlspecialchars($popularPost['title']), 60) ?>
                                            </a>
                                        </h6>
                                        <small class="text-muted">
                                            <i class="fas fa-eye me-1"></i><?= number_format($popularPost['views']) ?> visualizações
                                        </small>
                                    </div>
                                </div>
                                <?php endforeach; ?>
                            </div>
                        </div>

                        <!-- Recent Posts -->
                        <div class="card mb-4">
                            <div class="card-header bg-success text-white">
                                <h5 class="mb-0"><i class="fas fa-clock me-2"></i>Posts Recentes</h5>
                            </div>
                            <div class="card-body">
                                <?php foreach ($recentPosts as $recentPost): ?>
                                <div class="mb-3">
                                    <h6 class="mb-1">
                                        <a href="post.php?slug=<?= htmlspecialchars($recentPost['slug']) ?>" 
                                           class="text-decoration-none">
                                            <?= truncateText(htmlspecialchars($recentPost['title']), 70) ?>
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
                                <p class="card-text">Receba as melhores dicas sobre milhas aéreas diretamente no seu e-mail!</p>
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
                    <div class="social-links">
                        <a href="#" class="text-white me-3"><i class="fab fa-facebook-f"></i></a>
                        <a href="#" class="text-white me-3"><i class="fab fa-twitter"></i></a>
                        <a href="#" class="text-white me-3"><i class="fab fa-instagram"></i></a>
                        <a href="#" class="text-white me-3"><i class="fab fa-youtube"></i></a>
                    </div>
                </div>
                <div class="col-lg-3">
                    <h6>Categorias</h6>
                    <ul class="list-unstyled">
                        <?php foreach (array_slice($categories, 0, 4) as $category): ?>
                        <li class="mb-1">
                            <a href="index.php?category=<?= htmlspecialchars($category['slug']) ?>" 
                               class="text-muted text-decoration-none">
                                <?= htmlspecialchars($category['name']) ?>
                            </a>
                        </li>
                        <?php endforeach; ?>
                    </ul>
                </div>
                <div class="col-lg-3">
                    <h6>Links Úteis</h6>
                    <ul class="list-unstyled">
                        <li class="mb-1"><a href="admin/" class="text-muted text-decoration-none">Painel Admin</a></li>
                        <li class="mb-1"><a href="#" class="text-muted text-decoration-none">Sobre</a></li>
                        <li class="mb-1"><a href="#" class="text-muted text-decoration-none">Contato</a></li>
                        <li class="mb-1"><a href="#" class="text-muted text-decoration-none">Privacidade</a></li>
                    </ul>
                </div>
            </div>
            <hr class="my-4">
            <div class="row align-items-center">
                <div class="col-md-6">
                    <p class="mb-0 text-muted">
                        &copy; <?= date('Y') ?> Blog Milhas Aéreas. Desenvolvido por 
                        <a href="https://enigmasolutions.com.br" class="text-white">Enigma Solutions</a>
                    </p>
                </div>
                <div class="col-md-6 text-md-end">
                    <small class="text-muted">
                        <i class="fas fa-robot me-1"></i>Alguns conteúdos gerados por IA
                    </small>
                </div>
            </div>
        </div>
    </footer>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- Custom JS -->
    <script>
        // Smooth scrolling for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                document.querySelector(this.getAttribute('href')).scrollIntoView({
                    behavior: 'smooth'
                });
            });
        });

        // Auto-hide alerts
        setTimeout(() => {
            const alerts = document.querySelectorAll('.alert');
            alerts.forEach(alert => {
                if (alert.classList.contains('alert-info')) {
                    alert.style.transition = 'opacity 0.5s';
                    alert.style.opacity = '0.7';
                }
            });
        }, 5000);
    </script>
</body>
</html>