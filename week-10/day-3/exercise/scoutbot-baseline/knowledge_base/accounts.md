# Accounts and Access

A customer signs in with the email address used at purchase. If they cannot sign in, the first step
is a password reset from the sign-in page, which sends a reset link valid for one hour.

If the reset email does not arrive, ask the customer to check their spam folder and confirm they are
using the same email as on their order. A mismatched email is the usual reason a reset link seems to
never arrive: the account simply does not exist under the address they are trying.

Accounts are personal and tied to one email address. We can change the email on an account after
verifying ownership, but we cannot merge two separate accounts into one, so a customer with purchases
split across two emails keeps two separate histories.

Two-factor authentication is optional and can be enabled in account settings. If a customer is locked
out of their second factor, identity verification is required before we can disable it, and that step
cannot be skipped even for a long-standing customer.

The customer's plan, order history, and saved payment methods all live under the account. Deleting an
account is permanent and removes all of this after a 30-day grace period, during which the deletion
can still be reversed on request.

We never ask for a full password over chat or email. Any message that does is not from us, and a
customer who receives one should be told to ignore it and reset their password instead.
