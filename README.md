# 🛫 Blog Milhas Aéreas - Sistema de Publicação Automática com IA

Um blog completo sobre milhas aéreas e programas de fidelidade, desenvolvido em PHP com sistema de publicação automática usando Inteligência Artificial.

## 🚀 Características Principais

- **Frontend Responsivo**: Interface moderna com HTML5, CSS3 e Bootstrap 5
- **Backend PHP**: Arquitetura MVC robusta e escalável
- **Banco MySQL**: Schema otimizado para performance
- **IA Integrada**: Geração automática de conteúdo usando OpenAI
- **Sistema de Tags**: Organização inteligente do conteúdo
- **SEO Otimizado**: Meta tags, structured data e URLs amigáveis
- **Publicação Automática**: Cron jobs para postagem programada
- **Interface Admin**: Painel de controle para gerenciamento

## 🛠️ Tecnologias Utilizadas

### Frontend
- HTML5 semântico
- CSS3 com variáveis customizadas
- Bootstrap 5.3.2 para responsividade
- Font Awesome para ícones
- JavaScript vanilla para interações

### Backend
- PHP 8.0+ com orientação a objetos
- PDO para acesso ao banco de dados
- Composer para gerenciamento de dependências
- Arquitetura MVC personalizada

### Integrações
- OpenAI API para geração de conteúdo
- Unsplash para imagens automáticas
- Guzzle HTTP para requisições API

## 📋 Pré-requisitos

- PHP 8.0 ou superior
- MySQL 5.7 ou superior
- Composer
- Servidor web (Apache/Nginx)
- Conta OpenAI com API Key

## 🔧 Instalação

### 1. Clone o repositório
```bash
git clone <repository-url>
cd blog-milhas-aereas
```

### 2. Instale as dependências
```bash
composer install
```

### 3. Configure o banco de dados
```sql
mysql -u root -p < database/schema.sql
```

### 4. Configure as variáveis de ambiente
```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas configurações:
```env
# Banco de Dados
DB_HOST=localhost
DB_NAME=blog_milhas_aereas
DB_USER=root
DB_PASS=sua_senha

# OpenAI API
OPENAI_API_KEY=sua_api_key_aqui
AI_MODEL=gpt-3.5-turbo

# Configurações do Site
SITE_NAME="Blog Milhas Aéreas"
SITE_URL=http://localhost
ADMIN_EMAIL=admin@blogmilhas.com

# Publicação Automática
AUTO_POST_ENABLED=true
AUTO_POST_INTERVAL=24
MAX_POSTS_PER_DAY=3
```

### 5. Configure o servidor web

#### Apache (.htaccess)
```apache
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ index.php [QSA,L]
```

#### Nginx
```nginx
location / {
    try_files $uri $uri/ /index.php?$query_string;
}
```

### 6. Configure o cron job (opcional)
Para publicação automática, adicione ao crontab:
```bash
# Executa a cada 6 horas
0 */6 * * * php /caminho/para/projeto/cron/auto_publisher.php >> /var/log/blog_auto_publisher.log 2>&1
```

## 📁 Estrutura do Projeto

```
blog-milhas-aereas/
├── assets/
│   └── css/
│       └── style.css          # Estilos customizados
├── config/
│   └── bootstrap.php          # Configurações iniciais
├── cron/
│   └── auto_publisher.php     # Script de publicação automática
├── database/
│   └── schema.sql             # Schema do banco de dados
├── src/
│   ├── Config/
│   │   └── Database.php       # Configuração do banco
│   ├── Models/
│   │   ├── Post.php           # Modelo de posts
│   │   ├── Category.php       # Modelo de categorias
│   │   ├── Tag.php            # Modelo de tags
│   │   └── AILog.php          # Logs da IA
│   └── Services/
│       └── AIService.php      # Serviço de IA
├── index.php                  # Página principal
├── post.php                   # Página individual de post
├── composer.json              # Dependências PHP
├── .env.example               # Exemplo de configurações
└── README.md                  # Este arquivo
```

## 🎯 Funcionalidades

### 📝 Gerenciamento de Conteúdo
- Criação, edição e exclusão de posts
- Sistema de categorias e tags
- Upload de imagens
- Editor de markdown
- Agendamento de publicações

### 🤖 Inteligência Artificial
- Geração automática de artigos
- Sugestão de tópicos relevantes
- Criação de meta descriptions
- Tags automáticas baseadas no conteúdo
- Log detalhado de uso da API

### 📊 Analytics e SEO
- Contador de visualizações
- Meta tags otimizadas
- Structured data (JSON-LD)
- URLs amigáveis
- Sitemap automático

### 🎨 Interface do Usuário
- Design responsivo para todos os dispositivos
- Busca em tempo real
- Filtros por categoria
- Paginação inteligente
- Botões de compartilhamento social

## 🔐 Segurança

- Proteção contra XSS
- Headers de segurança
- Validação de entrada
- Sanitização de dados
- Prepared statements

## 🚀 Deploy em Produção

### 1. Configure HTTPS
```nginx
server {
    listen 443 ssl;
    server_name seudominio.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    root /var/www/blog-milhas-aereas;
    index index.php;
    
    location ~ \.php$ {
        fastcgi_pass unix:/var/run/php/php8.0-fpm.sock;
        fastcgi_index index.php;
        include fastcgi_params;
    }
}
```

### 2. Otimizações de Performance
- Configure cache de opcodes (OPcache)
- Use CDN para assets estáticos
- Configure compressão gzip
- Otimize consultas do banco

### 3. Backup Automático
```bash
# Script de backup diário
#!/bin/bash
mysqldump -u user -p blog_milhas_aereas > backup_$(date +%Y%m%d).sql
```

## 📈 Monitoramento

### Logs da Aplicação
- Logs de erro em `/var/log/php/`
- Logs de IA em banco de dados
- Logs de acesso do servidor web

### Métricas Importantes
- Posts gerados por dia
- Uso de tokens da OpenAI
- Taxa de visualizações
- Performance das consultas

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto é licenciado sob a MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 👨‍💻 Autor

**Augusto Gomes** - CEO da Enigma Solutions
- Website: [enigmasolutions.com.br](https://enigmasolutions.com.br)
- Email: comercial@enigmasolutions.com.br

## 🙏 Agradecimentos

- [OpenAI](https://openai.com) pela API de IA
- [Bootstrap](https://getbootstrap.com) pelo framework CSS
- [Font Awesome](https://fontawesome.com) pelos ícones
- [Unsplash](https://unsplash.com) pelas imagens

---

**⚡ Desenvolvido com dedicação para o mercado de milhas aéreas brasileiro**

