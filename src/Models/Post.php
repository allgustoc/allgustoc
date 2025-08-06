<?php

namespace App\Models;

use App\Config\Database;
use PDO;

class Post
{
    private $db;

    public function __construct()
    {
        $this->db = (new Database())->getConnection();
    }

    public function getAll($status = 'published', $limit = 10, $offset = 0): array
    {
        $sql = "SELECT p.*, c.name as category_name, c.color as category_color, c.slug as category_slug 
                FROM posts p 
                LEFT JOIN categories c ON p.category_id = c.id 
                WHERE p.status = :status 
                ORDER BY p.published_at DESC 
                LIMIT :limit OFFSET :offset";
        
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':status', $status);
        $stmt->bindParam(':limit', $limit, PDO::PARAM_INT);
        $stmt->bindParam(':offset', $offset, PDO::PARAM_INT);
        $stmt->execute();
        
        return $stmt->fetchAll();
    }

    public function getBySlug($slug): ?array
    {
        $sql = "SELECT p.*, c.name as category_name, c.color as category_color, c.slug as category_slug 
                FROM posts p 
                LEFT JOIN categories c ON p.category_id = c.id 
                WHERE p.slug = :slug AND p.status = 'published'";
        
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':slug', $slug);
        $stmt->execute();
        
        $post = $stmt->fetch();
        
        if ($post) {
            // Incrementar visualizações
            $this->incrementViews($post['id']);
            
            // Buscar tags do post
            $post['tags'] = $this->getPostTags($post['id']);
        }
        
        return $post ?: null;
    }

    public function getByCategory($categorySlug, $limit = 10, $offset = 0): array
    {
        $sql = "SELECT p.*, c.name as category_name, c.color as category_color, c.slug as category_slug 
                FROM posts p 
                JOIN categories c ON p.category_id = c.id 
                WHERE c.slug = :category_slug AND p.status = 'published' 
                ORDER BY p.published_at DESC 
                LIMIT :limit OFFSET :offset";
        
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':category_slug', $categorySlug);
        $stmt->bindParam(':limit', $limit, PDO::PARAM_INT);
        $stmt->bindParam(':offset', $offset, PDO::PARAM_INT);
        $stmt->execute();
        
        return $stmt->fetchAll();
    }

    public function create($data): int
    {
        $sql = "INSERT INTO posts (title, slug, excerpt, content, featured_image, category_id, status, is_ai_generated, ai_prompt, scheduled_at, published_at) 
                VALUES (:title, :slug, :excerpt, :content, :featured_image, :category_id, :status, :is_ai_generated, :ai_prompt, :scheduled_at, :published_at)";
        
        $stmt = $this->db->prepare($sql);
        
        $publishedAt = $data['status'] === 'published' ? date('Y-m-d H:i:s') : $data['published_at'] ?? null;
        
        $stmt->execute([
            ':title' => $data['title'],
            ':slug' => $data['slug'],
            ':excerpt' => $data['excerpt'],
            ':content' => $data['content'],
            ':featured_image' => $data['featured_image'],
            ':category_id' => $data['category_id'],
            ':status' => $data['status'],
            ':is_ai_generated' => $data['is_ai_generated'] ?? false,
            ':ai_prompt' => $data['ai_prompt'] ?? null,
            ':scheduled_at' => $data['scheduled_at'] ?? null,
            ':published_at' => $publishedAt
        ]);
        
        return $this->db->lastInsertId();
    }

    public function update($id, $data): bool
    {
        $sql = "UPDATE posts SET title = :title, slug = :slug, excerpt = :excerpt, content = :content, 
                featured_image = :featured_image, category_id = :category_id, status = :status, 
                scheduled_at = :scheduled_at, published_at = :published_at, updated_at = NOW() 
                WHERE id = :id";
        
        $stmt = $this->db->prepare($sql);
        
        return $stmt->execute([
            ':id' => $id,
            ':title' => $data['title'],
            ':slug' => $data['slug'],
            ':excerpt' => $data['excerpt'],
            ':content' => $data['content'],
            ':featured_image' => $data['featured_image'],
            ':category_id' => $data['category_id'],
            ':status' => $data['status'],
            ':scheduled_at' => $data['scheduled_at'] ?? null,
            ':published_at' => $data['published_at']
        ]);
    }

    public function delete($id): bool
    {
        $sql = "DELETE FROM posts WHERE id = :id";
        $stmt = $this->db->prepare($sql);
        return $stmt->execute([':id' => $id]);
    }

    public function getScheduledPosts(): array
    {
        $sql = "SELECT * FROM posts WHERE status = 'scheduled' AND scheduled_at <= NOW()";
        $stmt = $this->db->prepare($sql);
        $stmt->execute();
        return $stmt->fetchAll();
    }

    public function publishScheduledPost($id): bool
    {
        $sql = "UPDATE posts SET status = 'published', published_at = NOW() WHERE id = :id";
        $stmt = $this->db->prepare($sql);
        return $stmt->execute([':id' => $id]);
    }

    public function search($query, $limit = 10): array
    {
        $sql = "SELECT p.*, c.name as category_name, c.color as category_color 
                FROM posts p 
                LEFT JOIN categories c ON p.category_id = c.id 
                WHERE p.status = 'published' AND (p.title LIKE :query OR p.content LIKE :query OR p.excerpt LIKE :query)
                ORDER BY p.published_at DESC 
                LIMIT :limit";
        
        $stmt = $this->db->prepare($sql);
        $searchTerm = "%{$query}%";
        $stmt->bindParam(':query', $searchTerm);
        $stmt->bindParam(':limit', $limit, PDO::PARAM_INT);
        $stmt->execute();
        
        return $stmt->fetchAll();
    }

    public function getPostTags($postId): array
    {
        $sql = "SELECT t.* FROM tags t 
                JOIN post_tags pt ON t.id = pt.tag_id 
                WHERE pt.post_id = :post_id";
        
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':post_id', $postId);
        $stmt->execute();
        
        return $stmt->fetchAll();
    }

    public function addPostTags($postId, $tagIds): bool
    {
        // Primeiro, remove tags existentes
        $this->removeAllPostTags($postId);
        
        if (empty($tagIds)) {
            return true;
        }
        
        $sql = "INSERT INTO post_tags (post_id, tag_id) VALUES ";
        $values = [];
        $params = [':post_id' => $postId];
        
        foreach ($tagIds as $index => $tagId) {
            $values[] = "(:post_id, :tag_id_{$index})";
            $params[":tag_id_{$index}"] = $tagId;
        }
        
        $sql .= implode(', ', $values);
        
        $stmt = $this->db->prepare($sql);
        return $stmt->execute($params);
    }

    public function removeAllPostTags($postId): bool
    {
        $sql = "DELETE FROM post_tags WHERE post_id = :post_id";
        $stmt = $this->db->prepare($sql);
        return $stmt->execute([':post_id' => $postId]);
    }

    private function incrementViews($postId): bool
    {
        $sql = "UPDATE posts SET views = views + 1 WHERE id = :id";
        $stmt = $this->db->prepare($sql);
        return $stmt->execute([':id' => $postId]);
    }

    public function getTotalCount($status = 'published'): int
    {
        $sql = "SELECT COUNT(*) FROM posts WHERE status = :status";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':status', $status);
        $stmt->execute();
        return $stmt->fetchColumn();
    }

    public function getMostViewed($limit = 5): array
    {
        $sql = "SELECT p.*, c.name as category_name FROM posts p 
                LEFT JOIN categories c ON p.category_id = c.id 
                WHERE p.status = 'published' 
                ORDER BY p.views DESC 
                LIMIT :limit";
        
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':limit', $limit, PDO::PARAM_INT);
        $stmt->execute();
        
        return $stmt->fetchAll();
    }

    public function getRecent($limit = 5): array
    {
        $sql = "SELECT p.*, c.name as category_name FROM posts p 
                LEFT JOIN categories c ON p.category_id = c.id 
                WHERE p.status = 'published' 
                ORDER BY p.published_at DESC 
                LIMIT :limit";
        
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':limit', $limit, PDO::PARAM_INT);
        $stmt->execute();
        
        return $stmt->fetchAll();
    }
}