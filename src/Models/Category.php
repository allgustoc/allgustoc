<?php

namespace App\Models;

use App\Config\Database;
use PDO;

class Category
{
    private $db;

    public function __construct()
    {
        $this->db = (new Database())->getConnection();
    }

    public function getAll(): array
    {
        $sql = "SELECT * FROM categories ORDER BY name";
        $stmt = $this->db->prepare($sql);
        $stmt->execute();
        return $stmt->fetchAll();
    }

    public function getBySlug($slug): ?array
    {
        $sql = "SELECT * FROM categories WHERE slug = :slug";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':slug', $slug);
        $stmt->execute();
        return $stmt->fetch() ?: null;
    }

    public function create($data): int
    {
        $sql = "INSERT INTO categories (name, slug, description, color) VALUES (:name, :slug, :description, :color)";
        $stmt = $this->db->prepare($sql);
        $stmt->execute([
            ':name' => $data['name'],
            ':slug' => $data['slug'],
            ':description' => $data['description'],
            ':color' => $data['color']
        ]);
        return $this->db->lastInsertId();
    }

    public function update($id, $data): bool
    {
        $sql = "UPDATE categories SET name = :name, slug = :slug, description = :description, color = :color WHERE id = :id";
        $stmt = $this->db->prepare($sql);
        return $stmt->execute([
            ':id' => $id,
            ':name' => $data['name'],
            ':slug' => $data['slug'],
            ':description' => $data['description'],
            ':color' => $data['color']
        ]);
    }

    public function delete($id): bool
    {
        $sql = "DELETE FROM categories WHERE id = :id";
        $stmt = $this->db->prepare($sql);
        return $stmt->execute([':id' => $id]);
    }

    public function getWithPostCount(): array
    {
        $sql = "SELECT c.*, COUNT(p.id) as post_count 
                FROM categories c 
                LEFT JOIN posts p ON c.id = p.category_id AND p.status = 'published'
                GROUP BY c.id 
                ORDER BY c.name";
        $stmt = $this->db->prepare($sql);
        $stmt->execute();
        return $stmt->fetchAll();
    }
}