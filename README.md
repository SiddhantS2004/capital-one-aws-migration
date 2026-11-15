# Capital One-inspired Credit Application Centre (IT457 PoC)

A small Flask + PostgreSQL application for demonstrating local Docker deployment, EC2 lift-and-shift, and refactoring the database to Amazon RDS.

## Features
- Eight-field demo credit-card application form.
- Automatically generated application reference and database timestamp.
- Automatically assigned initial status (`Received`) for new submissions.
- Dashboard metrics and searchable recent-applications table.
- Four synthetic sample records inserted on first initialization.
- `/health` endpoint checks database connectivity.
- Existing `customers` table is not modified or deleted.

This is a classroom proof of concept, not an official Capital One service. It does not perform credit checks, make lending decisions, or collect SSNs, card numbers, or bank credentials.

## Local Docker deployment
1. Copy `.env.example` to `.env` if you want to customize settings (the defaults work without it).
2. Run:
   ```bash
   docker compose up --build -d
   ```
3. Open `http://localhost:5000`.
4. Submit a sample application and confirm it appears in the table.
5. Verify database records:
   ```bash
   docker exec -it capital-one-db psql -U postgres -d capitalone
   SELECT application_ref, full_name, card_type, application_status FROM applications ORDER BY id;
   ```
6. Test the health endpoint: `http://localhost:5000/health`.

## EC2 lift-and-shift
Copy the project folder to the EC2 VM and run the same local compose command:
```bash
sudo docker compose up --build -d
```
Open `http://EC2_PUBLIC_IP:5000` (ensure the EC2 security group allows TCP 5000 from your current IP).

## RDS refactored deployment
Use a separate environment file on EC2; do not commit or share it:
```bash
nano .env.rds
```
Add:
```dotenv
DATABASE_URL=postgresql://postgres:YOUR_RDS_PASSWORD@YOUR_RDS_ENDPOINT:5432/capitalone
FLASK_SECRET_KEY=your-private-demo-key
```
Then run:
```bash
sudo docker compose --env-file .env.rds -f docker-compose.rds.yml up --build -d
```
The RDS security group must allow PostgreSQL TCP 5432 from the EC2 security group. The RDS database must contain the `capitalone` database. On first application start, the app creates the separate `applications` table automatically.

The RDS compose file contains only the web service; it does not start a PostgreSQL container on EC2. Keep the old EC2 database container/volume untouched until you have verified the RDS application and data.

## Database notes
- `applications` is a new table; the previous `customers` table remains intact.
- The four synthetic demo records are inserted only when no demo records exist.
- New records are marked `is_demo = FALSE`.
- Do not enter real customer or financial data. Use fictional test data only.
- Never paste database passwords into chat or screenshots. Keep `.env` and `.env.rds` private.
