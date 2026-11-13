# Quick Cart – GPS-Based Local Shopping and Pre-Ordering System

Quick Cart is a Flask and MySQL mini project. Customers can discover shops, browse products and place pre-orders. Shop owners can manage products and update order status.

## Implemented features
- Customer and shop-owner registration/login
- Password hashing
- Shop product management
- Browser GPS location capture for shop owners
- Nearby shop search using the Haversine distance formula
- Product selection and order placement
- Shop confirmation, rejection and packed status
- Customer order history and order details

## Requirements
- Python 3.10+
- MySQL Server
- VS Code or another code editor
- A modern browser
- Internet/secure context for browser geolocation (localhost is allowed for development)

## Setup on Ubuntu

1. Start MySQL:
   ```bash
   sudo systemctl start mysql
   sudo systemctl status mysql
   ```

2. Create and enter the project folder, then create a virtual environment:
   ```bash
   cd quick_cart_project
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create environment configuration:
   ```bash
   cp .env.example .env
   nano .env
   ```
   Set your MySQL username and password. Change `SECRET_KEY` to a long random value. Do not upload `.env` to GitHub.

5. Run the application:
   ```bash
   python app.py
   ```
   The app creates the `quick_cart` database and required tables automatically. Open `http://127.0.0.1:5000`.

## First-time testing
1. Register a shop-owner account.
2. Log in as the shop owner, save the current GPS location and add products.
3. Log out and register a customer account.
4. Log in as the customer, allow location permission and search nearby shops.
5. Open a shop, choose product quantities and place an order.
6. Log out and log in as the shop owner. Confirm the order and mark it Packed.
7. Log back in as the customer and check the order status.

For a simple local test, the customer and shop can be tested in separate browser profiles. The GPS feature may require HTTPS on deployed sites; localhost is normally treated as a secure development origin.

## Important scope notes
- This is a college-project MVP, not a production payment or delivery system.
- The current order flow is for one selected shop per order. The PPT's optional “any nearby shop / first eligible shop confirms” workflow is a future extension because it needs a shared product catalogue, shop-offer/claim logic and transaction-safe order assignment.
- Push notifications, payment gateway, maps display, product image uploads, stock-editing UI, email verification, CSRF protection, admin panel and production deployment hardening are not included yet.
- Use HTTPS in deployment. Add CSRF protection, rate limiting, input validation and secure secret management before public use.
