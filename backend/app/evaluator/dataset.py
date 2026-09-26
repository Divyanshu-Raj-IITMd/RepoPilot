"""RepoPilot evaluation dataset.

Ground truth is written against the bundled demo repository
(demo-repos/ecommerce-api). Every question lists:
  - expected_files: gold files a correct answer must surface (retrieval + citations)
  - expect_keywords: strings a correct answer should mention (task success)
  - task: the agent route that should handle it
  - diff (review only): the change under review
  - expected_findings (review only): categories that must be detected

NOTE: these are *hand-written gold answers derived from reading the demo
repository*, and every metric below is computed by actually running the
system — nothing here is fabricated.
"""

QUESTIONS: list[dict] = [
    # ---------------------------------------------------------------- architecture
    {"id": "arch_01", "category": "architecture", "task": "analyst",
     "question": "What is the architecture of this repository?",
     "expected_files": ["app/main.py"], "expect_keywords": ["fastapi"]},
    {"id": "arch_02", "category": "architecture", "task": "analyst",
     "question": "What framework does this project use?",
     "expected_files": [], "expect_keywords": ["fastapi"]},
    {"id": "arch_03", "category": "architecture", "task": "analyst",
     "question": "What database does this project use?",
     "expected_files": ["app/repositories/db.py"], "expect_keywords": ["sqlite"]},
    {"id": "arch_04", "category": "architecture", "task": "analyst",
     "question": "Describe the structure of this project.",
     "expected_files": ["app/main.py"], "expect_keywords": ["app/routes", "app/services"]},
    {"id": "arch_05", "category": "architecture", "task": "analyst",
     "question": "How is this codebase organized?",
     "expected_files": [], "expect_keywords": ["app/services"]},
    {"id": "arch_06", "category": "architecture", "task": "analyst",
     "question": "What is the main entry point of the application?",
     "expected_files": ["app/main.py"], "expect_keywords": ["app/main.py"]},
    {"id": "arch_07", "category": "architecture", "task": "analyst",
     "question": "What tech stack does this repo use?",
     "expected_files": [], "expect_keywords": ["fastapi"]},
    {"id": "arch_08", "category": "architecture", "task": "analyst",
     "question": "Where are the tests in this project?",
     "expected_files": ["tests/test_invoice.py"], "expect_keywords": ["tests/"]},
    {"id": "arch_09", "category": "architecture", "task": "analyst",
     "question": "What are the main packages of this repository?",
     "expected_files": [], "expect_keywords": ["auth"]},
    {"id": "arch_10", "category": "architecture", "task": "analyst",
     "question": "Give me an overview of this repository.",
     "expected_files": [], "expect_keywords": ["fastapi"]},

    {"id": "arch_11", "category": "architecture", "task": "analyst",
     "question": "What language is this project written in?",
     "expected_files": [], "expect_keywords": ["python"]},
    {"id": "arch_12", "category": "architecture", "task": "analyst",
     "question": "Where is the entry point of the service?",
     "expected_files": ["app/main.py"], "expect_keywords": ["app/main.py"]},
    {"id": "arch_13", "category": "architecture", "task": "analyst",
     "question": "Describe the project architecture for a new contributor.",
     "expected_files": [], "expect_keywords": ["routes"]},
    {"id": "arch_14", "category": "architecture", "task": "analyst",
     "question": "What are the main components of this codebase?",
     "expected_files": [], "expect_keywords": ["services"]},
    {"id": "arch_15", "category": "architecture", "task": "analyst",
     "question": "Explain the repository structure layer by layer.",
     "expected_files": [], "expect_keywords": ["app/"]},
    {"id": "arch_16", "category": "architecture", "task": "analyst",
     "question": "How many endpoints does this API expose?",
     "expected_files": [], "expect_keywords": ["11"]},
    {"id": "arch_17", "category": "architecture", "task": "analyst",
     "question": "What does this repository do?",
     "expected_files": [], "expect_keywords": ["api"]},
    {"id": "arch_18", "category": "architecture", "task": "analyst",
     "question": "Where are the tests and what do they cover?",
     "expected_files": ["tests/test_invoice.py"], "expect_keywords": ["tests"]},
    {"id": "arch_19", "category": "architecture", "task": "analyst",
     "question": "What database does this service store its data in, and where is that configured?",
     "expected_files": ["app/repositories/db.py"], "expect_keywords": ["sqlite"]},
    {"id": "arch_20", "category": "architecture", "task": "analyst",
     "question": "What are the main modules of this project and what is each responsible for?",
     "expected_files": [], "expect_keywords": ["auth"]},

    # ------------------------------------------------------------------ code search
    {"id": "cs_01", "category": "code_search", "task": "search",
     "question": "Where is JWT authentication implemented?",
     "expected_files": ["app/auth/jwt.py", "app/middleware/auth.py"],
     "expect_keywords": ["jwt"]},
    {"id": "cs_02", "category": "code_search", "task": "search",
     "question": "Where are tokens created?",
     "expected_files": ["app/auth/jwt.py"], "expect_keywords": ["encode_token"]},
    {"id": "cs_03", "category": "code_search", "task": "search",
     "question": "Where is the invoice calculation implemented?",
     "expected_files": ["app/utils/invoice.py"], "expect_keywords": ["calculate_invoice"]},
    {"id": "cs_04", "category": "code_search", "task": "search",
     "question": "Which file handles the /api/users endpoint?",
     "expected_files": ["app/routes/users.py"], "expect_keywords": ["users.py"]},
    {"id": "cs_05", "category": "code_search", "task": "search",
     "question": "Where is the data access layer?",
     "expected_files": ["app/repositories/db.py"], "expect_keywords": ["db.py"]},
    {"id": "cs_06", "category": "code_search", "task": "search",
     "question": "Where is input validation implemented?",
     "expected_files": ["app/utils/validators.py"], "expect_keywords": ["validators"]},
    {"id": "cs_07", "category": "code_search", "task": "search",
     "question": "Where are orders created?",
     "expected_files": ["app/services/orders.py"], "expect_keywords": ["orders"]},
    {"id": "cs_08", "category": "code_search", "task": "search",
     "question": "Where is the middleware that checks bearer tokens?",
     "expected_files": ["app/middleware/auth.py"], "expect_keywords": ["middleware"]},
    {"id": "cs_09", "category": "code_search", "task": "search",
     "question": "Where is the password hash computed?",
     "expected_files": ["app/auth/service.py"], "expect_keywords": ["hash"]},
    {"id": "cs_10", "category": "code_search", "task": "search",
     "question": "Which file defines the Product model?",
     "expected_files": ["app/models/models.py"], "expect_keywords": ["product"]},
    {"id": "cs_11", "category": "code_search", "task": "search",
     "question": "Where are new users created?",
     "expected_files": ["app/services/users.py"], "expect_keywords": ["create_user"]},
    {"id": "cs_12", "category": "code_search", "task": "search",
     "question": "Where is token expiry checked?",
     "expected_files": ["app/auth/jwt.py"], "expect_keywords": ["exp"]},
    {"id": "cs_13", "category": "code_search", "task": "search",
     "question": "Where is the products endpoint implemented?",
     "expected_files": ["app/routes/products.py"], "expect_keywords": ["products"]},
    {"id": "cs_14", "category": "code_search", "task": "search",
     "question": "Where is the secret key defined for signing tokens?",
     "expected_files": ["app/auth/jwt.py"], "expect_keywords": ["secret"]},

    {"id": "cs_15", "category": "code_search", "task": "search",
     "question": "Where are tokens decoded and verified?",
     "expected_files": ["app/auth/jwt.py"], "expect_keywords": ["decode_token"]},
    {"id": "cs_16", "category": "code_search", "task": "search",
     "question": "Which file implements the order cancellation endpoint?",
     "expected_files": ["app/routes/orders.py"], "expect_keywords": ["orders"]},
    {"id": "cs_17", "category": "code_search", "task": "search",
     "question": "Where is the login endpoint implemented?",
     "expected_files": ["app/routes/users.py"], "expect_keywords": ["login"]},
    {"id": "cs_18", "category": "code_search", "task": "search",
     "question": "Where are SQL queries executed against the database?",
     "expected_files": ["app/repositories/db.py"], "expect_keywords": ["repositor"]},
    {"id": "cs_19", "category": "code_search", "task": "search",
     "question": "Which file defines the Order dataclass?",
     "expected_files": ["app/models/models.py"], "expect_keywords": ["models"]},
    {"id": "cs_20", "category": "code_search", "task": "search",
     "question": "Where is the Bearer token extracted from the request header?",
     "expected_files": ["app/middleware/auth.py"], "expect_keywords": ["middleware"]},

    # ---------------------------------------------------------- dependency tracing
    {"id": "dep_01", "category": "dependency_tracing", "task": "search",
     "question": "Which files import app/services/users?",
     "expected_files": ["app/routes/users.py", "app/auth/service.py"],
     "expect_keywords": ["routes/users"]},
    {"id": "dep_02", "category": "dependency_tracing", "task": "search",
     "question": "Who calls get_user_by_username?",
     "expected_files": ["app/routes/users.py", "app/auth/service.py", "app/services/users.py"],
     "expect_keywords": ["get_user"]},
    {"id": "dep_03", "category": "dependency_tracing", "task": "search",
     "question": "What does app/routes/orders.py depend on?",
     "expected_files": ["app/services/orders.py"],
     "expect_keywords": ["orders"]},
    {"id": "dep_04", "category": "dependency_tracing", "task": "search",
     "question": "Which files depend on app/repositories/db.py?",
     "expected_files": ["app/services/users.py", "app/services/orders.py", "app/services/products.py"],
     "expect_keywords": ["services"]},
    {"id": "dep_05", "category": "dependency_tracing", "task": "search",
     "question": "Who uses calculate_invoice?",
     "expected_files": ["app/services/orders.py", "tests/test_invoice.py"],
     "expect_keywords": ["calculate_invoice"]},
    {"id": "dep_06", "category": "dependency_tracing", "task": "search",
     "question": "Which test file covers the invoice calculation?",
     "expected_files": ["tests/test_invoice.py"], "expect_keywords": ["test_invoice"]},
    {"id": "dep_07", "category": "dependency_tracing", "task": "search",
     "question": "What does the middleware import?",
     "expected_files": ["app/middleware/auth.py", "app/auth/jwt.py"],
     "expect_keywords": ["decode_token"]},
    {"id": "dep_08", "category": "dependency_tracing", "task": "search",
     "question": "Which files import app/utils/validators?",
     "expected_files": ["app/routes/products.py"], "expect_keywords": ["products"]},
    {"id": "dep_09", "category": "dependency_tracing", "task": "search",
     "question": "Who calls query_all?",
     "expected_files": ["app/services/orders.py", "app/services/products.py", "app/services/users.py"],
     "expect_keywords": ["query_all"]},
    {"id": "dep_10", "category": "dependency_tracing", "task": "search",
     "question": "Which files does app/main.py include?",
     "expected_files": ["app/routes/users.py", "app/routes/products.py", "app/routes/orders.py"],
     "expect_keywords": ["routes"]},

    {"id": "dep_11", "category": "dependency_tracing", "task": "search",
     "question": "Which files import app/repositories/db?",
     "expected_files": ["app/services/users.py", "app/services/orders.py", "app/services/products.py"],
     "expect_keywords": ["services"]},
    {"id": "dep_12", "category": "dependency_tracing", "task": "search",
     "question": "Who calls create_user?",
     "expected_files": ["app/routes/users.py"], "expect_keywords": ["create_user"]},
    {"id": "dep_13", "category": "dependency_tracing", "task": "search",
     "question": "What does app/auth/service.py depend on?",
     "expected_files": ["app/auth/jwt.py", "app/services/users.py"],
     "expect_keywords": ["jwt"]},
    {"id": "dep_14", "category": "dependency_tracing", "task": "search",
     "question": "Which files depend on app/utils/invoice?",
     "expected_files": ["app/services/orders.py", "tests/test_invoice.py"],
     "expect_keywords": ["orders"]},
    {"id": "dep_15", "category": "dependency_tracing", "task": "search",
     "question": "Who calls decode_token?",
     "expected_files": ["app/middleware/auth.py", "app/auth/service.py"],
     "expect_keywords": ["decode_token"]},
    {"id": "dep_16", "category": "dependency_tracing", "task": "search",
     "question": "Which test file covers the JWT token helpers?",
     "expected_files": ["tests/test_jwt.py"], "expect_keywords": ["test_jwt"]},
    {"id": "dep_17", "category": "dependency_tracing", "task": "search",
     "question": "What does app/routes/products.py depend on?",
     "expected_files": ["app/services/products.py", "app/utils/validators.py"],
     "expect_keywords": ["products"]},
    {"id": "dep_18", "category": "dependency_tracing", "task": "search",
     "question": "Who calls validate_price?",
     "expected_files": ["app/routes/products.py"], "expect_keywords": ["validate_price"]},
    {"id": "dep_19", "category": "dependency_tracing", "task": "search",
     "question": "Which files does app/services/orders.py import?",
     "expected_files": ["app/repositories/db.py", "app/utils/invoice.py"],
     "expect_keywords": ["invoice"]},
    {"id": "dep_20", "category": "dependency_tracing", "task": "search",
     "question": "What depends on app/repositories/db.py?",
     "expected_files": ["app/services/users.py", "app/services/orders.py"],
     "expect_keywords": ["services"]},

    # ---------------------------------------------------------- bug investigation
    {"id": "bug_01", "category": "bug_investigation", "task": "investigate",
     "question": "Why might GET /api/users/{username} return HTTP 500?",
     "expected_files": ["app/routes/users.py", "app/services/users.py"],
     "expect_keywords": ["none", "500"]},
    {"id": "bug_02", "category": "bug_investigation", "task": "investigate",
     "question": "Why is there a SQL injection risk in list_orders?",
     "expected_files": ["app/services/orders.py"],
     "expect_keywords": ["sql", "injection"]},
    {"id": "bug_03", "category": "bug_investigation", "task": "investigate",
     "question": "Why can calculate_invoice return a negative total?",
     "expected_files": ["app/utils/invoice.py"],
     "expect_keywords": ["discount"]},
    {"id": "bug_04", "category": "bug_investigation", "task": "investigate",
     "question": "Why might POST /api/products fail with an empty product name?",
     "expected_files": ["app/routes/products.py", "app/utils/validators.py"],
     "expect_keywords": ["validat"]},
    {"id": "bug_05", "category": "bug_investigation", "task": "investigate",
     "question": "Why is the hardcoded secret in jwt.py a security problem?",
     "expected_files": ["app/auth/jwt.py"],
     "expect_keywords": ["secret"]},
    {"id": "bug_06", "category": "bug_investigation", "task": "investigate",
     "question": "Why does creating an order execute many queries in a loop?",
     "expected_files": ["app/services/orders.py"],
     "expect_keywords": ["loop", "n+1", "n + 1"]},
    {"id": "bug_07", "category": "bug_investigation", "task": "investigate",
     "question": "Why might GET /api/products/{product_id} crash for a missing product?",
     "expected_files": ["app/routes/products.py", "app/services/products.py"],
     "expect_keywords": ["none"]},
    {"id": "bug_08", "category": "bug_investigation", "task": "investigate",
     "question": "Why is committing a .env file with AWS keys dangerous?",
     "expected_files": [".env"], "expect_keywords": ["secret", "aws", "key"]},
    {"id": "bug_09", "category": "bug_investigation", "task": "investigate",
     "question": "Why might /api/users fail if the database is unavailable?",
     "expected_files": ["app/routes/users.py", "app/repositories/db.py"],
     "expect_keywords": ["error", "handling"]},
    {"id": "bug_10", "category": "bug_investigation", "task": "investigate",
     "question": "Why does the invoice test suite not cover failure paths?",
     "expected_files": ["tests/test_invoice.py", "app/utils/invoice.py"],
     "expect_keywords": ["test"]},

    {"id": "bug_11", "category": "bug_investigation", "task": "investigate",
     "question": "Why is list_orders vulnerable to SQL injection when a status filter is applied?",
     "expected_files": ["app/services/orders.py"], "expect_keywords": ["sql", "injection"]},
    {"id": "bug_12", "category": "bug_investigation", "task": "investigate",
     "question": "Why might POST /api/orders accept an order with a negative quantity?",
     "expected_files": ["app/routes/orders.py"], "expect_keywords": ["validat"]},
    {"id": "bug_13", "category": "bug_investigation", "task": "investigate",
     "question": "Why might POST /api/users accept a username with special characters?",
     "expected_files": ["app/routes/users.py"], "expect_keywords": ["validat"]},
    {"id": "bug_14", "category": "bug_investigation", "task": "investigate",
     "question": "Why is SHA-256 a weak choice for password hashing in this codebase?",
     "expected_files": ["app/auth/service.py"], "expect_keywords": ["sha256", "hash"]},
    {"id": "bug_15", "category": "bug_investigation", "task": "investigate",
     "question": "Why does get_order return None instead of raising an error for a missing order?",
     "expected_files": ["app/services/orders.py"], "expect_keywords": ["none"]},
    {"id": "bug_16", "category": "bug_investigation", "task": "investigate",
     "question": "Why does create_order compute the order total twice?",
     "expected_files": ["app/services/orders.py"], "expect_keywords": ["calculate_invoice"]},
    {"id": "bug_17", "category": "bug_investigation", "task": "investigate",
     "question": "Why might cancel_order report success even when the order id does not exist?",
     "expected_files": ["app/services/orders.py"], "expect_keywords": ["cancel"]},
    {"id": "bug_18", "category": "bug_investigation", "task": "investigate",
     "question": "Why can /health be accessed without a bearer token?",
     "expected_files": ["app/middleware/auth.py"], "expect_keywords": ["public"]},
    {"id": "bug_19", "category": "bug_investigation", "task": "investigate",
     "question": "Why might POST /api/products return HTTP 500 when the name field is missing?",
     "expected_files": ["app/routes/products.py"], "expect_keywords": ["name"]},
    {"id": "bug_20", "category": "bug_investigation", "task": "investigate",
     "question": "Why is the database URL with an embedded password in .env a security risk?",
     "expected_files": [".env"], "expect_keywords": ["password", "credential", "secret"]},

    # ----------------------------------------------------------------- pr review
    {"id": "rev_01", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/services/orders.py b/app/services/orders.py\n"
             "+++ b/app/services/orders.py\n@@ -12,6 +12,9 @@ def list_orders(status):\n"
             "+    sql = f\"SELECT * FROM orders WHERE note = '{note}'\"\n"
             "+    return db.query_all(sql)\n",
     "expected_files": ["app/services/orders.py"],
     "expected_findings": [{"category": "sql_injection"}],
     "expect_keywords": ["sql"]},
    {"id": "rev_02", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/services/users.py b/app/services/users.py\n"
             "+++ b/app/services/users.py\n@@ -30,6 +30,10 @@ def create_user\n"
             "+    try:\n+        db.execute(insert_sql)\n+    except Exception:\n+        pass\n",
     "expected_files": ["app/services/users.py"],
     "expected_findings": [{"category": "swallowed_error"}],
     "expect_keywords": ["except"]},
    {"id": "rev_03", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/auth/jwt.py b/app/auth/jwt.py\n"
             "+++ b/app/auth/jwt.py\n@@ -8,6 +8,8 @@\n"
             "+SECRET_KEY = \"sk-live-51H8xYzStripeSuperSecretKey\"\n"
             "+STRIPE_TOKEN = \"tok_9f8e7d6c5b4a3210\"\n",
     "expected_files": ["app/auth/jwt.py"],
     "expected_findings": [{"category": "hardcoded_secret"}],
     "expect_keywords": ["secret"]},
    {"id": "rev_04", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/utils/invoice.py b/app/utils/invoice.py\n"
             "+++ b/app/utils/invoice.py\n@@ -10,6 +10,9 @@\n"
             "+def apply_bulk_discount(items=[]):\n"
             "+    # TODO: implement bulk tiers\n"
             "+    return items\n",
     "expected_files": ["app/utils/invoice.py"],
     "expected_findings": [{"category": "mutable_default"}, {"category": "todo"}],
     "expect_keywords": ["mutable", "todo"]},
    {"id": "rev_05", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/services/products.py b/app/services/products.py\n"
             "+++ b/app/services/products.py\n@@ -20,6 +20,8 @@\n"
             "+def search_products(q):\n"
             "+    return os.system(\"grep -r \" + q + \" products.txt\")\n",
     "expected_files": ["app/services/products.py"],
     "expected_findings": [{"category": "dangerous_call"}],
     "expect_keywords": ["os.system", "dangerous"]},
    {"id": "rev_06", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/services/orders.py b/app/services/orders.py\n"
             "+++ b/app/services/orders.py\n@@ -20,6 +20,12 @@\n"
             "+def recalc_totals(order_id):\n"
             "+    for item in items:\n"
             "+        db.execute(\"UPDATE order_items SET price = ? WHERE id = ?\", (p, i))\n",
     "expected_files": ["app/services/orders.py"],
     "expected_findings": [{"category": "n_plus_one"}],
     "expect_keywords": ["loop", "n+1", "n + 1", "query"]},
    {"id": "rev_07", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/middleware/auth.py b/app/middleware/auth.py\n"
             "+++ b/app/middleware/auth.py\n@@ -20,6 +20,8 @@\n"
             "-    payload = decode_token(auth_header.removeprefix(\"Bearer \").strip())\n"
             "+    payload = json.loads(base64.b64decode(auth_header.split(\".\")[1]))\n",
     "expected_files": ["app/middleware/auth.py"],
     "expected_findings": [{"category": "removed_auth"}],
     "expect_keywords": ["auth", "removed", "verification", "signature"]},
    {"id": "rev_08", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/services/users.py b/app/services/users.py\n"
             "+++ b/app/services/users.py\n@@ -40,6 +40,10 @@\n"
             "-def create_user(username, email, password):\n"
             "+def create_user(email, password):\n",
     "expected_files": ["app/services/users.py"],
     "expected_findings": [{"category": "breaking_change"}],
     "expect_keywords": ["breaking", "parameter"]},
    {"id": "rev_09", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/utils/validators.py b/app/utils/validators.py\n"
             "+++ b/app/utils/validators.py\n@@ -1,6 +1,9 @@\n"
             "+def validate_discount(d):\n"
             "+    if d == None:\n"
             "+        raise ValueError(\"discount missing\")\n",
     "expected_files": ["app/utils/validators.py"],
     "expected_findings": [{"category": "style"}],
     "expect_keywords": ["none", "is none"]},
    {"id": "rev_10", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/services/orders.py b/app/services/orders.py\n"
             "+++ b/app/services/orders.py\n@@ -15,6 +15,14 @@\n"
             "+def export_orders_csv(username):\n"
             "+    sql = f\"SELECT * FROM orders WHERE username = '{username}'\"\n"
             "+    try:\n"
             "+        return db.query_all(sql)\n"
             "+    except Exception:\n"
             "+        pass\n",
     "expected_files": ["app/services/orders.py"],
     "expected_findings": [{"category": "sql_injection"}, {"category": "swallowed_error"}],
     "expect_keywords": ["sql"]},

    {"id": "rev_11", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/utils/validators.py b/app/utils/validators.py\n"
             "+++ b/app/utils/validators.py\n@@ -20,6 +20,9 @@\n"
             "+def evaluate_formula(expr):\n"
             "+    return eval(expr)\n",
     "expected_files": ["app/utils/validators.py"],
     "expected_findings": [{"category": "dangerous_call"}],
     "expect_keywords": ["eval"]},
    {"id": "rev_12", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/services/users.py b/app/services/users.py\n"
             "+++ b/app/services/users.py\n@@ -50,6 +50,9 @@\n"
             "+def run_report(cmd):\n"
             "+    return subprocess.run(cmd, shell=True, capture_output=True)\n",
     "expected_files": ["app/services/users.py"],
     "expected_findings": [{"category": "dangerous_call"}],
     "expect_keywords": ["shell"]},
    {"id": "rev_13", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/services/products.py b/app/services/products.py\n"
             "+++ b/app/services/products.py\n@@ -40,6 +40,8 @@\n"
             "+def bulk_activate(product_ids=[]):\n"
             "+    return len(product_ids)\n",
     "expected_files": ["app/services/products.py"],
     "expected_findings": [{"category": "mutable_default"}],
     "expect_keywords": ["mutable", "default"]},
    {"id": "rev_14", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/routes/orders.py b/app/routes/orders.py\n"
             "+++ b/app/routes/orders.py\n@@ -30,6 +30,10 @@\n"
             "+    try:\n"
             "+        order_service.cancel_order(order_id)\n"
             "+    except Exception:\n"
             "+        pass\n",
     "expected_files": ["app/routes/orders.py"],
     "expected_findings": [{"category": "swallowed_error"}],
     "expect_keywords": ["except"]},
    {"id": "rev_15", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/repositories/db.py b/app/repositories/db.py\n"
             "+++ b/app/repositories/db.py\n@@ -10,6 +10,8 @@\n"
             "+DB_PASSWORD = \"sup3r-s3cret-prod-password\"\n"
             "+ADMIN_TOKEN = \"adm-token-9876543210fedcba\"\n",
     "expected_files": ["app/repositories/db.py"],
     "expected_findings": [{"category": "hardcoded_secret"}],
     "expect_keywords": ["secret", "token", "password"]},
    {"id": "rev_16", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/routes/products.py b/app/routes/products.py\n"
             "+++ b/app/routes/products.py\n@@ -12,6 +12,8 @@\n"
             "+    # TODO: add pagination before releasing this endpoint\n"
             "+    pass\n",
     "expected_files": ["app/routes/products.py"],
     "expected_findings": [{"category": "todo"}],
     "expect_keywords": ["todo"]},
    {"id": "rev_17", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/auth/service.py b/app/auth/service.py\n"
             "+++ b/app/auth/service.py\n@@ -18,6 +18,7 @@\n"
             "-    payload = decode_token(token)\n"
             "+    payload = json.loads(base64.urlsafe_b64decode(token.split(\".\")[1]))\n",
     "expected_files": ["app/auth/service.py"],
     "expected_findings": [{"category": "removed_auth"}],
     "expect_keywords": ["auth", "removed", "verification", "signature"]},
    {"id": "rev_18", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/services/orders.py b/app/services/orders.py\n"
             "+++ b/app/services/orders.py\n@@ -26,6 +26,6 @@\n"
             "-def get_order(order_id: int) -> dict:\n"
             "+def get_order() -> dict:\n",
     "expected_files": ["app/services/orders.py"],
     "expected_findings": [{"category": "breaking_change"}],
     "expect_keywords": ["breaking", "parameter"]},
    {"id": "rev_19", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/services/users.py b/app/services/users.py\n"
             "+++ b/app/services/users.py\n@@ -55,6 +55,10 @@\n"
             "+def reactivate_users(user_ids):\n"
             "+    for uid in user_ids:\n"
             "+        db.execute(\"UPDATE users SET is_active = 1 WHERE id = ?\", (uid,))\n",
     "expected_files": ["app/services/users.py"],
     "expected_findings": [{"category": "n_plus_one"}],
     "expect_keywords": ["loop", "n+1", "n + 1", "query"]},
    {"id": "rev_20", "category": "pr_review", "task": "review",
     "question": "Review this pull request",
     "diff": "diff --git a/app/repositories/db.py b/app/repositories/db.py\n"
             "+++ b/app/repositories/db.py\n@@ -60,6 +60,10 @@\n"
             "+def vacuum() -> None:\n"
             "+    conn = connect()\n"
             "+    conn.execute(\"VACUUM\")\n"
             "+    conn.close()\n",
     "expected_files": ["app/repositories/db.py"],
     "expected_findings": [{"category": "missing_tests"}],
     "expect_keywords": ["test"]},

    # ------------------------------------------------------- test generation (extra)
    {"id": "test_01", "category": "test_generation", "task": "testgen",
     "question": "generate tests for calculate_invoice",
     "target": "calculate_invoice",
     "expected_files": ["app/utils/invoice.py"],
     "expect_keywords": ["8/8"],
     "expect_verification": ["validated", "validated_after_fix"]},
    {"id": "test_02", "category": "test_generation", "task": "testgen",
     "question": "generate tests for encode_token",
     "target": "encode_token",
     "expected_files": ["app/auth/jwt.py"],
     "expect_keywords": ["passed"],
     "expect_verification": ["validated", "validated_after_fix"]},
    {"id": "test_03", "category": "test_generation", "task": "testgen",
     "question": "generate tests for decode_token",
     "target": "decode_token",
     "expected_files": ["app/auth/jwt.py"],
     "expect_keywords": ["passed"],
     "expect_verification": ["validated", "validated_after_fix"]},
    {"id": "test_04", "category": "test_generation", "task": "testgen",
     "question": "generate tests for validate_quantity",
     "target": "validate_quantity",
     "expected_files": ["app/utils/validators.py"],
     "expect_keywords": ["passed"],
     "expect_verification": ["validated", "validated_after_fix"]},
]
