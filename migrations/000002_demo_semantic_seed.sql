INSERT INTO sources (spider_name, display_name, domain, country, organization, legacy_table, updated_at)
VALUES
    ('demo_global', 'Demo Global Wire', 'demo.example.com', '德国', '欧盟', 'demo_global', CURRENT_TIMESTAMP),
    ('demo_us_tech', 'Demo US Tech', 'demo-us.example.com', '美国', 'OpenAI', 'demo_us_tech', CURRENT_TIMESTAMP),
    ('demo_energy_asia', 'Demo Energy Asia', 'demo-asia.example.com', '印尼', '东盟', 'demo_energy_asia', CURRENT_TIMESTAMP)
ON CONFLICT (spider_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    domain = EXCLUDED.domain,
    country = EXCLUDED.country,
    organization = EXCLUDED.organization,
    legacy_table = EXCLUDED.legacy_table,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO articles (
    source_id,
    source_url,
    title_original,
    content_original,
    publish_time,
    author,
    language,
    section,
    country,
    organization,
    category,
    legacy_table,
    content_hash,
    translation_status,
    embedding_status,
    updated_at
)
SELECT
    s.id,
    seed.source_url,
    seed.title_original,
    seed.content_original,
    seed.publish_time,
    seed.author,
    seed.language,
    seed.section,
    seed.country,
    seed.organization,
    seed.category,
    seed.legacy_table,
    seed.content_hash,
    'completed',
    'completed',
    CURRENT_TIMESTAMP
FROM (
    VALUES
        (
            'demo_global',
            'https://demo.example.com/eu-ai-liability',
            'EU approves AI liability framework',
            'The European Union approved a new AI liability framework focused on enterprise accountability, model governance, and cross-border compliance for generative AI vendors.',
            TIMESTAMP '2025-06-09 09:00:00',
            'Demo Editor',
            'en',
            'policy',
            '德国',
            '欧盟',
            '法规',
            'demo_global',
            'demo-eu-ai-liability'
        ),
        (
            'demo_global',
            'https://demo.example.com/eu-ai-governance-fines',
            'EU finalizes governance rules and fines for AI providers',
            'European regulators finalized governance obligations and financial penalties for AI providers operating in the single market, with new compliance checkpoints for frontier models.',
            TIMESTAMP '2025-06-10 11:30:00',
            'Demo Editor',
            'en',
            'policy',
            '德国',
            '欧盟',
            '法规',
            'demo_global',
            'demo-eu-ai-governance-fines'
        ),
        (
            'demo_us_tech',
            'https://demo-us.example.com/openai-europe-compliance',
            'OpenAI expands Europe compliance team after new EU rules',
            'OpenAI expanded its Europe compliance team and internal governance process after new EU rules raised requirements on disclosure, risk management, and enterprise readiness.',
            TIMESTAMP '2025-06-11 14:20:00',
            'Demo Tech Desk',
            'en',
            'technology',
            '美国',
            'OpenAI',
            '科技',
            'demo_us_tech',
            'demo-openai-europe-compliance'
        ),
        (
            'demo_energy_asia',
            'https://demo-asia.example.com/asean-energy-transition',
            'ASEAN summit highlights regional energy transition financing',
            'ASEAN leaders highlighted transition financing, grid modernization, and LNG investment coordination during a regional energy summit focused on industrial resilience.',
            TIMESTAMP '2025-06-07 08:40:00',
            'Demo Asia Desk',
            'en',
            'economy',
            '印尼',
            '东盟',
            '环境',
            'demo_energy_asia',
            'demo-asean-energy-transition'
        )
) AS seed(
    spider_name,
    source_url,
    title_original,
    content_original,
    publish_time,
    author,
    language,
    section,
    country,
    organization,
    category,
    legacy_table,
    content_hash
)
JOIN sources s ON s.spider_name = seed.spider_name
ON CONFLICT (source_url) DO UPDATE SET
    title_original = EXCLUDED.title_original,
    content_original = EXCLUDED.content_original,
    publish_time = EXCLUDED.publish_time,
    author = EXCLUDED.author,
    language = EXCLUDED.language,
    section = EXCLUDED.section,
    country = EXCLUDED.country,
    organization = EXCLUDED.organization,
    category = EXCLUDED.category,
    legacy_table = EXCLUDED.legacy_table,
    content_hash = EXCLUDED.content_hash,
    translation_status = 'completed',
    embedding_status = 'completed',
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO article_translations (
    article_id,
    target_language,
    title_translated,
    summary_translated,
    content_translated,
    translator,
    status,
    updated_at
)
SELECT
    a.id,
    'zh-CN',
    seed.title_translated,
    seed.summary_translated,
    seed.content_translated,
    'demo-seed',
    'completed',
    CURRENT_TIMESTAMP
FROM (
    VALUES
        (
            'https://demo.example.com/eu-ai-liability',
            '欧盟通过人工智能责任框架',
            '欧盟批准新的人工智能责任框架，重点约束企业问责、模型治理和跨境合规。',
            '欧盟批准新的人工智能责任框架，重点约束企业问责、模型治理以及生成式人工智能厂商的跨境合规要求。'
        ),
        (
            'https://demo.example.com/eu-ai-governance-fines',
            '欧盟敲定人工智能治理规则与罚款机制',
            '欧洲监管机构敲定 AI 提供商治理义务与罚款机制，强化前沿模型合规检查。',
            '欧洲监管机构敲定针对人工智能提供商的治理义务与罚款机制，并增加针对前沿模型的合规检查节点。'
        ),
        (
            'https://demo-us.example.com/openai-europe-compliance',
            'OpenAI 因欧盟新规扩充欧洲合规团队',
            'OpenAI 在欧盟新规出台后扩大欧洲合规与治理团队，应对披露和风险管理要求。',
            '在欧盟新规出台后，OpenAI 扩大了欧洲合规团队和内部治理流程，以满足披露、风险管理和企业级准备要求。'
        ),
        (
            'https://demo-asia.example.com/asean-energy-transition',
            '东盟峰会聚焦区域能源转型融资',
            '东盟领导人在峰会上强调能源转型融资、电网升级和 LNG 投资协调。',
            '东盟领导人在区域能源峰会上强调能源转型融资、电网现代化以及液化天然气投资协调，重点关注产业韧性。'
        )
) AS seed(source_url, title_translated, summary_translated, content_translated)
JOIN articles a ON a.source_url = seed.source_url
ON CONFLICT (article_id, target_language) DO UPDATE SET
    title_translated = EXCLUDED.title_translated,
    summary_translated = EXCLUDED.summary_translated,
    content_translated = EXCLUDED.content_translated,
    translator = EXCLUDED.translator,
    status = 'completed',
    updated_at = CURRENT_TIMESTAMP;

DELETE FROM article_embeddings
WHERE article_id IN (
    SELECT id
    FROM articles
    WHERE source_url IN (
        'https://demo.example.com/eu-ai-liability',
        'https://demo.example.com/eu-ai-governance-fines',
        'https://demo-us.example.com/openai-europe-compliance',
        'https://demo-asia.example.com/asean-energy-transition'
    )
);

DELETE FROM article_chunks
WHERE article_id IN (
    SELECT id
    FROM articles
    WHERE source_url IN (
        'https://demo.example.com/eu-ai-liability',
        'https://demo.example.com/eu-ai-governance-fines',
        'https://demo-us.example.com/openai-europe-compliance',
        'https://demo-asia.example.com/asean-energy-transition'
    )
);

INSERT INTO article_chunks (
    article_id,
    chunk_index,
    content_text,
    token_count,
    embedding_status,
    updated_at
)
SELECT
    a.id,
    0,
    seed.content_text,
    seed.token_count,
    'completed',
    CURRENT_TIMESTAMP
FROM (
    VALUES
        (
            'https://demo.example.com/eu-ai-liability',
            '欧盟批准新的人工智能责任框架，重点约束企业问责、模型治理以及生成式人工智能厂商的跨境合规要求。',
            38
        ),
        (
            'https://demo.example.com/eu-ai-governance-fines',
            '欧洲监管机构敲定针对人工智能提供商的治理义务与罚款机制，并增加针对前沿模型的合规检查节点。',
            40
        ),
        (
            'https://demo-us.example.com/openai-europe-compliance',
            '在欧盟新规出台后，OpenAI 扩大了欧洲合规团队和内部治理流程，以满足披露、风险管理和企业级准备要求。',
            42
        ),
        (
            'https://demo-asia.example.com/asean-energy-transition',
            '东盟领导人在区域能源峰会上强调能源转型融资、电网现代化以及液化天然气投资协调，重点关注产业韧性。',
            36
        )
) AS seed(source_url, content_text, token_count)
JOIN articles a ON a.source_url = seed.source_url;

INSERT INTO article_embeddings (
    article_id,
    chunk_id,
    chunk_index,
    embedding_model,
    embedding_dimensions,
    embedding_vector,
    updated_at
)
SELECT
    a.id,
    c.id,
    0,
    'demo-semantic-v1',
    4,
    seed.embedding_vector::jsonb,
    CURRENT_TIMESTAMP
FROM (
    VALUES
        ('https://demo.example.com/eu-ai-liability', '[0.95, 0.88, 0.12, 0.05]'),
        ('https://demo.example.com/eu-ai-governance-fines', '[0.93, 0.91, 0.08, 0.04]'),
        ('https://demo-us.example.com/openai-europe-compliance', '[0.84, 0.73, 0.22, 0.07]'),
        ('https://demo-asia.example.com/asean-energy-transition', '[0.08, 0.10, 0.95, 0.82]')
 ) AS seed(source_url, embedding_vector)
JOIN articles a ON a.source_url = seed.source_url
JOIN article_chunks c ON c.article_id = a.id AND c.chunk_index = 0
ON CONFLICT (article_id, chunk_index, embedding_model) DO UPDATE SET
    chunk_id = EXCLUDED.chunk_id,
    embedding_dimensions = EXCLUDED.embedding_dimensions,
    embedding_vector = EXCLUDED.embedding_vector,
    updated_at = CURRENT_TIMESTAMP;

UPDATE articles
SET translation_status = 'completed',
    embedding_status = 'completed',
    updated_at = CURRENT_TIMESTAMP
WHERE source_url IN (
    'https://demo.example.com/eu-ai-liability',
    'https://demo.example.com/eu-ai-governance-fines',
    'https://demo-us.example.com/openai-europe-compliance',
    'https://demo-asia.example.com/asean-energy-transition'
);
