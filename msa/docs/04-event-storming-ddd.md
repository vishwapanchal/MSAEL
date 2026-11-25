# 04 - Event Storming and DDD

Notation: command (a request to do something), event (past-tense fact), aggregate (consistency boundary), policy ("whenever X then Y"), read model (what queries need).

## Checkout (inferred from `src/checkoutservice/main.go`)
```mermaid
flowchart LR
  C1[Command: PlaceOrder] --> A1((Aggregate: Order))
  A1 --> E1[Event: OrderPrepared]
  E1 --> P1{{Policy: charge then ship}}
  P1 --> E2[Event: PaymentCharged]
  E2 --> E3[Event: OrderShipped]
  E3 --> E4[Event: CartEmptied]
  E3 --> E5[Event: ConfirmationEmailSent]
```
These events are conceptual: checkoutservice does not persist or publish them (I found no data store in it; the result is returned as `PlaceOrderResponse`). Other aggregates: Cart (cartservice), Product (catalog, read-only). Read models: cart view, product list.

## Reviews
```mermaid
flowchart LR
  c1[Submit review] --> A((Aggregate: Review))
  c2[Edit review] --> A
  c3[Remove review] --> A
  A --> e1[ReviewSubmitted]
  A --> e2[ReviewEdited]
  A --> e3[ReviewRemoved]
  e1 --> pol{{Policy: apply event to projection}}
  e2 --> pol
  e3 --> pol
  pol --> rm1[(Read model: reviews per product)]
  pol --> rm2[(Read model: rating summary per product)]
```
- Aggregate **Review**, identified by `review_id`; edit and remove only make sense for an existing review.
- Events are stored in `events(seq, review_id, type, payload_json, created_at)`.
- Policy: every event updates the projection; `POST /admin/rebuild-projection` replays all events.
- Read models: review list and rating summary per `product_id`.

## Bounded contexts
```mermaid
flowchart LR
  subgraph Catalog
   PCS[productcatalogservice]
  end
  subgraph Ordering
   CART[cart] --- CO[checkout] --- PAY[payment] --- SHIP[shipping]
  end
  subgraph Reviews
   RS[reviews-service]
  end
  Reviews -. product_id string only .- Catalog
```
The word "product" means different things: in Catalog it is a record with price and picture; in Reviews it is only an opaque `product_id` string. That is why no shared model or runtime call is needed.

## Why reviews is its own service
- Different data shape and write pattern (append-only user content vs a static catalog file).
- Different change rate: review features can ship without redeploying catalog or checkout.
- Failure isolation: if reviews is down, browsing and checkout still work.
- No transaction spans reviews and orders.
- Separate team ownership (doc 02).

## Sizing reasoning
One aggregate, three commands, two queries, one event table plus projection: small enough for one team to understand fully, big enough to justify its own deployment. We did not split commands and queries into two services because a SQLite file on one PVC cannot safely be written by two processes and the load does not justify it (doc 05).

## How this maps to the syllabus
Event storming, DDD (aggregates, bounded contexts, ubiquitous language), service granularity.

## Evidence in this repo
- `src/checkoutservice/main.go`, `protos/demo.proto`
- `msa/services/reviews-service`, `msa/api/reviews-openapi.yaml`
