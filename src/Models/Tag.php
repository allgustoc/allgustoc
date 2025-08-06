<?php

namespace App\Models;

use App\Config\Database;
use PDO;

class Tag
{
    private $db;

    public function __construct()
    {
        $this->db = (new Database())->getConnection();
    }

    public function getAll(): array
    {
        $sql = "SELECT * FROM tags ORDER BY name";
        $stmt = $this->db->prepare($sql);
        $stmt->execute();
        return $stmt->fetchAll();
    }

    public function getByName($name): ?array
    {
        $sql = "SELECT * FROM tags WHERE name = :name";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':name', $name);
        $stmt->execute();
        return $stmt->fetch() ?: null;
    }

    public function getBySlug($slug): ?array
    {
        $sql = "SELECT * FROM tags WHERE slug = :slug";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':slug', $slug);
        $stmt->execute();
        return $stmt->fetch() ?: null;
    }

    public function create($data): int
    {
        $sql = "INSERT INTO tags (name, slug) VALUES (:name, :slug)";
        $stmt = $this->db->prepare($sql);
        $stmt->execute([
            ':name' => $data['name'],
            ':slug' => $data['slug']
        ]);
        return $this->db->lastInsertId();
    }

    public function update($id, $data): bool
    {
        $sql = "UPDATE tags SET name = :name, slug = :slug WHERE id = :id";
        $stmt = $this->db->prepare($sql);
        return $stmt->execute([
            ':id' => $id,
            ':name' => $data['name'],
            ':slug' => $data['slug']
        ]);
    }

    public function delete($id): bool
    {
        $sql = "DELETE FROM tags WHERE id = :id";
        $stmt = $this->db->prepare($sql);
        return $stmt->execute([':id' => $id]);
    }

    public function getWithPostCount(): array
    {
        $sql = "SELECT t.*, COUNT(pt.post_id) as post_count 
                FROM tags t 
                LEFT JOIN post_tags pt ON t.id = pt.tag_id 
                LEFT JOIN posts p ON pt.post_id = p.id AND p.status = 'published'
                GROUP BY t.id 
                ORDER BY post_count DESC, t.name";
        $stmt = $this->db->prepare($sql);
        $stmt->execute();
        return $stmt->fetchAll();
    }

    public function getMostUsed($limit = 10): array
    {
        $sql = "SELECT t.*, COUNT(pt.post_id) as post_count 
                FROM tags t 
                JOIN post_tags pt ON t.id = pt.tag_id 
                JOIN posts p ON pt.post_id = p.id AND p.status = 'published'
                GROUP BY t.id 
                ORDER BY post_count DESC 
                LIMIT :limit";
        
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':limit', $limit, PDO::PARAM_INT);
        $stmt->execute();
        return $stmt->fetchAll();
    }
}