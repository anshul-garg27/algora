# OpenAPI Design-First Approach (Bullet 5)

> **Resume Bullet:** "Implemented OpenAPI design-first API development, reducing integration time by 30%"

---

## What Is Design-First?

Design-first means **the API specification is the source of truth**, written BEFORE implementation code.

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                        DESIGN-FIRST WORKFLOW                                    │
│                                                                                 │
│  Step 1: WRITE THE SPEC                                                        │
│  ├── Define endpoints, request/response schemas                                │
│  ├── Add validation rules (required fields, patterns, sizes)                   │
│  ├── Write examples for every scenario (success, errors)                       │
│  └── Review spec with consumers (frontend, partner teams)                      │
│                                                                                 │
│  Step 2: SHARE SPEC IMMEDIATELY                                                │
│  ├── Consumers generate client SDKs from spec                                  │
│  ├── Consumers mock responses using examples                                   │
│  ├── Frontend development starts IN PARALLEL                                   │
│  └── No waiting for backend code!                                              │
│                                                                                 │
│  Step 3: BUILD IMPLEMENTATION                                                   │
│  ├── Generate server stubs from spec (openapi-generator-maven-plugin)          │
│  ├── Implement business logic against generated interfaces                     │
│  └── Implementation MUST match spec exactly                                    │
│                                                                                 │
│  Step 4: VALIDATE WITH R2C                                                      │
│  ├── R2C (Request-to-Contract) tests run automatically                         │
│  ├── Compare actual API responses against spec                                 │
│  └── Fail build if implementation doesn't match contract                       │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## How I Did It (PR #260: +898 lines)

### 1. Defined the Endpoint

```json
{
  "path": "/inventory/search-distribution-center-status",
  "method": "POST",
  "description": "Search inventory status across distribution centers",
  "request": {
    "body": {
      "items": ["array of GTINs"],
      "siteId": "US | CA | MX"
    }
  },
  "responses": {
    "200": "Inventory data by DC and type",
    "400": "Invalid request (bad GTIN format, too many items)",
    "401": "Unauthorized",
    "404": "No data found",
    "500": "Internal server error"
  }
}
```

### 2. Wrote Request/Response Schemas

```json
// inventory_search_distribution_center_status_request.json
{
  "items": [
    {
      "gtin": "00012345678905",
      "wmItemNbr": 12345
    }
  ],
  "siteId": "US"
}

// inventory_search_distribution_center_status_response_200.json
{
  "inventoryItems": [
    {
      "gtin": "00012345678905",
      "distributionCenters": [
        {
          "dcNumber": "6012",
          "inventoryByType": [
            {
              "inventoryType": "ON_HAND",
              "quantity": 1500
            },
            {
              "inventoryType": "IN_TRANSIT",
              "quantity": 300
            }
          ]
        }
      ]
    }
  ]
}
```

### 3. Wrote Error Examples

```json
// All error combination example
{
  "errors": [
    {
      "gtin": "00012345678905",
      "errorCode": "GTIN_NOT_FOUND",
      "message": "No inventory data found for this GTIN"
    },
    {
      "gtin": "INVALID_FORMAT",
      "errorCode": "INVALID_GTIN",
      "message": "GTIN must be 14 digits"
    }
  ]
}
```

### 4. API Spec File Structure

```
api-spec/
├── openapi_consolidated.json                                    # Full OpenAPI 3.0 spec
├── examples/
│   ├── inventory_search_distribution_center_status_request.json
│   ├── inventory_search_distribution_center_status_response_200.json
│   ├── ...response_all_error_combination.json
│   ├── ...response_success_error_combination.json
│   ├── notify_...invalid_length_error_400.json
│   ├── notify_...invalid_property_error_400.json
│   └── notify_...malformed_error_400.json
├── schema/
│   ├── common/
│   │   ├── inventory.json
│   │   ├── inventory_by_location_item.json
│   │   ├── inventory_by_state.json
│   │   └── inventory_item.json
│   └── (dc inventory specific schemas)
└── doc/
    └── userguide.md
```

---

## Why Design-First Matters (Interview Talking Points)

### 1. Parallel Development
> "While I was building the implementation, the consumer team was already coding their integration using the spec. They generated a client SDK and mocked responses. By the time my implementation was ready, they just pointed their client to the real endpoint and it worked."

### 2. Contract as Documentation
> "The spec IS the documentation. It defines every field, every validation rule, every error scenario. New team members read the spec instead of the code."

### 3. R2C Contract Testing
> "We integrated R2C (Request-to-Contract) testing into our CI pipeline. Every build validates that the actual API responses match the spec. If I change the response format without updating the spec, the build fails."

### 4. Consistent Error Handling
> "The spec defines error response schemas for every HTTP status code. This means consumers know exactly what error format to expect - no surprises."

---

## Interview Questions

### Q: "What does design-first mean in practice?"
> "Design-first means writing the OpenAPI spec before any code. The spec defines request/response schemas, validation rules, error codes, and includes examples. We use openapi-generator-maven-plugin to generate server stubs from the spec. Consumers can start integration immediately using the spec while I build the implementation. R2C testing validates the implementation matches the contract."

### Q: "How does this differ from code-first?"
> "In code-first, you write the controller, then generate the spec from annotations. The problem: consumers wait for your code, and the spec is an afterthought - it may not capture all edge cases. In design-first, the spec is reviewed and agreed upon before coding starts. It's the contract."

### Q: "How did this reduce integration time by 30%?"
> "Without design-first, the consumer team would wait 3-4 weeks for my implementation before starting integration. With the spec available from day one, they started in parallel - generating client SDKs, mocking responses, building their UI. When my implementation was ready, integration was mostly done. We saved about 30% of the total end-to-end delivery time."

### Q: "What is R2C testing?"
> "R2C stands for Request-to-Contract. It's automated testing that sends requests to your API and validates the responses against the OpenAPI spec. It checks response schemas, status codes, header formats. If you change the API without updating the spec, R2C fails. It's our guarantee that spec and implementation stay in sync."

---

*Next: [03-dc-inventory-implementation.md](./03-dc-inventory-implementation.md) - Implementation deep dive*
