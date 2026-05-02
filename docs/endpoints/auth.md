# Auth

User registration, login, profile, and user management with JWT authentication.

**Base path:** `/api/v1/auth`

---

## Register

`POST /api/v1/auth/register`

Create a new user account and receive a JWT token.

### Request Body

| Field | Type | Description |
|:------|:-----|:------------|
| `username` | string | Unique username |
| `email` | string | Valid email address |
| `password` | string | Password |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "securepass123"}'
```

### Example Response

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "role": "user"
  }
}
```

---

## Login

`POST /api/v1/auth/login`

Authenticate and receive a JWT token.

### Request Body

| Field | Type | Description |
|:------|:-----|:------------|
| `username` | string | Username |
| `password` | string | Password |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "securepass123"}'
```

### Example Response

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "role": "user"
  }
}
```

---

## Get Current User

`GET /api/v1/auth/me`

Returns the authenticated user's profile. Requires a valid JWT token.

### Example Request

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  http://localhost:8000/api/v1/auth/me
```

### Example Response

```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "role": "user"
}
```

---

## List Users

`GET /api/v1/auth/users`

List all registered users. **Requires admin role.**

### Example Request

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  http://localhost:8000/api/v1/auth/users
```

### Example Response

```json
[
  {"id": 1, "username": "alice", "email": "alice@example.com", "role": "user"},
  {"id": 2, "username": "admin", "email": "admin@example.com", "role": "admin"}
]
```
