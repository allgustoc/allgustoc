<?php

namespace App\Models;

use App\Config\Database;
use PDO;

class AILog
{
    private $db;

    public function __construct()
    {
        $this->db = (new Database())->getConnection();
    }

    public function create($data): int
    {
        $sql = "INSERT INTO ai_logs (prompt, response, model, tokens_used, cost, status, error_message, post_id) 
                VALUES (:prompt, :response, :model, :tokens_used, :cost, :status, :error_message, :post_id)";
        
        $stmt = $this->db->prepare($sql);
        $stmt->execute([
            ':prompt' => $data['prompt'],
            ':response' => $data['response'] ?? null,
            ':model' => $data['model'] ?? null,
            ':tokens_used' => $data['tokens_used'] ?? 0,
            ':cost' => $data['cost'] ?? 0,
            ':status' => $data['status'] ?? 'success',
            ':error_message' => $data['error_message'] ?? null,
            ':post_id' => $data['post_id'] ?? null
        ]);
        
        return $this->db->lastInsertId();
    }

    public function getAll($limit = 50, $offset = 0): array
    {
        $sql = "SELECT * FROM ai_logs ORDER BY created_at DESC LIMIT :limit OFFSET :offset";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':limit', $limit, PDO::PARAM_INT);
        $stmt->bindParam(':offset', $offset, PDO::PARAM_INT);
        $stmt->execute();
        return $stmt->fetchAll();
    }

    public function getByStatus($status, $limit = 50): array
    {
        $sql = "SELECT * FROM ai_logs WHERE status = :status ORDER BY created_at DESC LIMIT :limit";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':status', $status);
        $stmt->bindParam(':limit', $limit, PDO::PARAM_INT);
        $stmt->execute();
        return $stmt->fetchAll();
    }

    public function getStats(): array
    {
        $sql = "SELECT 
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_requests,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed_requests,
                    SUM(tokens_used) as total_tokens,
                    SUM(cost) as total_cost,
                    AVG(tokens_used) as avg_tokens_per_request
                FROM ai_logs";
        
        $stmt = $this->db->prepare($sql);
        $stmt->execute();
        return $stmt->fetch();
    }

    public function getUsageByDate($days = 30): array
    {
        $sql = "SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as requests,
                    SUM(tokens_used) as tokens,
                    SUM(cost) as cost
                FROM ai_logs 
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                GROUP BY DATE(created_at)
                ORDER BY date DESC";
        
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':days', $days, PDO::PARAM_INT);
        $stmt->execute();
        return $stmt->fetchAll();
    }

    public function deleteOldLogs($days = 90): int
    {
        $sql = "DELETE FROM ai_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL :days DAY)";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(':days', $days, PDO::PARAM_INT);
        $stmt->execute();
        return $stmt->rowCount();
    }
}