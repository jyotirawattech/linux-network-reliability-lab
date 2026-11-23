# When a lost acknowledgement duplicates work

A queue can redeliver a message after the consumer has already produced an
effect. This offline model lets you compare where to acknowledge and what a
retained marker can do. It supplies one logical message and a fixed sequence of
synthetic outcomes. Each attempted delivery consumes one outcome. Once the
broker settles the message, it makes no further deliveries in that run.

## Run the replay

```sh
make compare-delivery
```

The [worked JSON](../results/delivery-replay.json) contains every modeled
attempt and its ordered events. To check the exact result from a fresh run:

```sh
make -s compare-delivery | cmp - docs/results/delivery-replay.json
```

## Policies and assumptions

- **Ack first.** The effect runs only after the broker settles the message.
  If the ack is lost on its way to the broker, this policy skips the effect
  and a later attempt may still be processed. A crash after settlement but
  before the effect can lose work.
- **Ack last.** This is the baseline for duplicate effects. Run the effect,
  then ack. A crash or lost ack between those steps can leave committed work
  behind a message the broker can still redeliver.
- **Atomic effect and marker.** Ack last, with a modeled durable transaction
  that commits the effect and its marker together for the same logical ID.
  A later attempt finds the marker, suppresses the effect, and can still ack.

Each attempt has one outcome. `before_effect` and `after_effect` place a
crash on opposite sides of the effect step. `ack_lost` means the broker did
not receive the ack. There is no separate lost confirmation or in-flight
concurrency in this model.

## Worked comparison

Each cell lists **effects / attempts / broker settled** for the same input
outcomes. A second effect on the same message counts as a duplicate.

| Outcomes | Ack first | Ack last | Atomic effect and marker |
| --- | --- | --- | --- |
| Clean delivery | 1 / 1 / yes | 1 / 1 / yes | 1 / 1 / yes |
| Crash before effect, then clean | 0 / 1 / yes | 1 / 2 / yes | 1 / 2 / yes |
| Crash after effect, then clean | 1 / 1 / yes | 2 / 2 / yes | 1 / 2 / yes |
| Lost ack, then clean | 1 / 2 / yes | 2 / 2 / yes | 1 / 2 / yes |
| Two lost acks, budget exhausted | 0 / 2 / no | 2 / 2 / no | 1 / 2 / no |

For the lost-ack-then-clean case, the marker changes the result from **two
effects to one** at the same two attempts. This removes one duplicate in the
model. The crash-before-effect case shows the separate cost of early settlement.
It can end the queue's work with zero effects. Running out of attempts can leave
a message unsettled even when the marker protected against two effects.

For `k` supplied outcomes and `t` attempted deliveries, each policy takes
O(k) time including input validation and emits O(t) trace entries, with
`t <= k`. The simulation uses constant working state for one logical message
outside the returned trace. A real retained marker costs storage per distinct
ID and needs a retention policy covering the possible replay window. This
example models settlement and durability in a single sequential trace. A broker
and an actual storage engine would need separate tests to establish delivery or
exactly-once behavior. **Paired benchmark: Not run.** The numbers count events.
