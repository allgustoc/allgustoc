-- Schema do Blog de Milhas Aéreas
-- Criado em: 2024

CREATE DATABASE IF NOT EXISTS blog_milhas_aereas CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE blog_milhas_aereas;

-- Tabela de categorias
CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(7) DEFAULT '#007bff',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabela de tags
CREATE TABLE tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de posts
CREATE TABLE posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    excerpt TEXT,
    content LONGTEXT NOT NULL,
    featured_image VARCHAR(500),
    category_id INT,
    status ENUM('draft', 'published', 'scheduled') DEFAULT 'draft',
    is_ai_generated BOOLEAN DEFAULT FALSE,
    ai_prompt TEXT,
    views INT DEFAULT 0,
    likes INT DEFAULT 0,
    scheduled_at TIMESTAMP NULL,
    published_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
    INDEX idx_status (status),
    INDEX idx_published_at (published_at),
    INDEX idx_category (category_id),
    INDEX idx_slug (slug)
);

-- Tabela de relacionamento posts-tags
CREATE TABLE post_tags (
    post_id INT,
    tag_id INT,
    PRIMARY KEY (post_id, tag_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Tabela de configurações do sistema
CREATE TABLE settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabela de logs de IA
CREATE TABLE ai_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prompt TEXT NOT NULL,
    response LONGTEXT,
    model VARCHAR(50),
    tokens_used INT,
    cost DECIMAL(10,4),
    status ENUM('success', 'error') DEFAULT 'success',
    error_message TEXT,
    post_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE SET NULL
);

-- Inserir categorias iniciais
INSERT INTO categories (name, slug, description, color) VALUES
('Programas de Fidelidade', 'programas-fidelidade', 'Tudo sobre programas de milhagem das companhias aéreas', '#007bff'),
('Dicas de Acúmulo', 'dicas-acumulo', 'Como acumular milhas rapidamente', '#28a745'),
('Transferências', 'transferencias', 'Guias sobre transferência de milhas entre programas', '#ffc107'),
('Promoções', 'promocoes', 'Promoções e ofertas especiais de milhas', '#dc3545'),
('Cartões de Crédito', 'cartoes-credito', 'Melhores cartões para acumular milhas', '#6f42c1'),
('Viagens', 'viagens', 'Destinos e experiências usando milhas', '#fd7e14');

-- Inserir tags iniciais
INSERT INTO tags (name, slug) VALUES
('Azul', 'azul'),
('TAM', 'tam'),
('Gol', 'gol'),
('American Airlines', 'american-airlines'),
('United', 'united'),
('Cartão de Crédito', 'cartao-credito'),
('Promoção', 'promocao'),
('Dica', 'dica'),
('Transfer', 'transfer'),
('Primeira Classe', 'primeira-classe'),
('Executiva', 'executiva'),
('Nacional', 'nacional'),
('Internacional', 'internacional');

-- Inserir configurações iniciais
INSERT INTO settings (setting_key, setting_value, description) VALUES
('site_title', 'Blog Milhas Aéreas', 'Título do site'),
('site_description', 'O melhor conteúdo sobre milhas aéreas e programas de fidelidade', 'Descrição do site'),
('posts_per_page', '10', 'Número de posts por página'),
('auto_post_enabled', '1', 'Publicação automática habilitada'),
('auto_post_interval', '24', 'Intervalo entre posts automáticos (horas)'),
('max_posts_per_day', '3', 'Máximo de posts por dia'),
('openai_model', 'gpt-3.5-turbo', 'Modelo da OpenAI utilizado'),
('featured_image_default', 'https://source.unsplash.com/1200x600/?airplane,travel', 'Imagem padrão para posts');