"""Initial production schema and single-branch seed data.

Revision ID: 20260812_0001
Revises: None
"""

from alembic import op

revision = "20260812_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE staff_role AS ENUM ('admin', 'manager');
        CREATE TYPE order_status AS ENUM ('pending', 'confirmed', 'preparing', 'ready', 'out_for_delivery', 'delivered', 'cancelled');
        CREATE TYPE payment_method AS ENUM ('cash_on_delivery', 'safepay');
        CREATE TYPE payment_status AS ENUM ('pending', 'authorized', 'paid', 'failed', 'refunded');
        CREATE TYPE fulfillment_type AS ENUM ('delivery', 'pickup');
        CREATE TYPE discount_type AS ENUM ('percentage', 'fixed');
        CREATE TYPE campaign_status AS ENUM ('draft', 'scheduled', 'sending', 'sent', 'cancelled');
        CREATE TYPE notification_status AS ENUM ('pending', 'processing', 'sent', 'failed', 'skipped');
        CREATE TYPE refund_status AS ENUM ('requested', 'approved', 'processed', 'rejected');
        CREATE TYPE task_status AS ENUM ('todo', 'in_progress', 'done');
        CREATE SEQUENCE order_number_seq START 1001;

        CREATE TABLE staff_profiles (
          user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
          email varchar(320) NOT NULL UNIQUE,
          display_name varchar(120) NOT NULL,
          role staff_role NOT NULL,
          is_active boolean NOT NULL DEFAULT true,
          last_seen_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE store_settings (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(120) NOT NULL,
          phone varchar(20) NOT NULL, email varchar(320), address text NOT NULL,
          city varchar(80) NOT NULL DEFAULT 'Lahore', timezone varchar(50) NOT NULL DEFAULT 'Asia/Karachi',
          currency varchar(3) NOT NULL DEFAULT 'PKR', tax_rate_bps integer NOT NULL DEFAULT 0 CHECK (tax_rate_bps BETWEEN 0 AND 10000),
          default_delivery_fee integer NOT NULL DEFAULT 15000 CHECK (default_delivery_fee >= 0),
          minimum_order integer NOT NULL DEFAULT 50000 CHECK (minimum_order >= 0),
          free_delivery_threshold integer NOT NULL DEFAULT 250000 CHECK (free_delivery_threshold >= 0),
          accepts_delivery boolean NOT NULL DEFAULT true, accepts_pickup boolean NOT NULL DEFAULT false,
          orders_paused boolean NOT NULL DEFAULT false, opening_hours jsonb NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE delivery_zones (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(100) NOT NULL, areas jsonb NOT NULL DEFAULT '[]',
          delivery_fee integer NOT NULL CHECK (delivery_fee >= 0), minimum_order integer CHECK (minimum_order >= 0),
          free_delivery_threshold integer CHECK (free_delivery_threshold >= 0), estimated_minutes integer NOT NULL DEFAULT 45,
          is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE categories (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(100) NOT NULL, slug varchar(100) NOT NULL UNIQUE,
          sort_order integer NOT NULL DEFAULT 0, is_active boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE products (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), category_id uuid REFERENCES categories(id) ON DELETE SET NULL,
          name varchar(140) NOT NULL, slug varchar(140) NOT NULL UNIQUE, description text NOT NULL DEFAULT '',
          price integer NOT NULL CHECK (price > 0), compare_at_price integer CHECK (compare_at_price > 0),
          tag varchar(50), tone varchar(30), image_url text, is_available boolean NOT NULL DEFAULT true,
          is_featured boolean NOT NULL DEFAULT false, sort_order integer NOT NULL DEFAULT 0,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_products_category ON products(category_id);
        CREATE TABLE modifier_groups (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(100) NOT NULL,
          min_selections integer NOT NULL DEFAULT 0, max_selections integer NOT NULL DEFAULT 1,
          is_active boolean NOT NULL DEFAULT true, sort_order integer NOT NULL DEFAULT 0,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
          CHECK (min_selections >= 0 AND max_selections >= min_selections)
        );
        CREATE TABLE modifier_options (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), group_id uuid NOT NULL REFERENCES modifier_groups(id) ON DELETE CASCADE,
          name varchar(100) NOT NULL, price_delta integer NOT NULL DEFAULT 0,
          is_available boolean NOT NULL DEFAULT true, sort_order integer NOT NULL DEFAULT 0,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_modifier_options_group ON modifier_options(group_id);
        CREATE TABLE product_modifier_groups (
          product_id uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
          group_id uuid NOT NULL REFERENCES modifier_groups(id) ON DELETE CASCADE,
          PRIMARY KEY(product_id, group_id)
        );
        CREATE TABLE ingredients (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(120) NOT NULL, sku varchar(80) NOT NULL UNIQUE,
          unit varchar(20) NOT NULL CHECK (unit IN ('unit','gram','millilitre')),
          quantity_on_hand numeric(14,3) NOT NULL DEFAULT 0, reorder_level numeric(14,3) NOT NULL DEFAULT 0,
          is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE product_ingredients (
          product_id uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
          ingredient_id uuid NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
          quantity numeric(14,3) NOT NULL CHECK (quantity > 0), PRIMARY KEY(product_id, ingredient_id)
        );
        CREATE TABLE modifier_option_ingredients (
          option_id uuid NOT NULL REFERENCES modifier_options(id) ON DELETE CASCADE,
          ingredient_id uuid NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
          quantity numeric(14,3) NOT NULL CHECK (quantity > 0), PRIMARY KEY(option_id, ingredient_id)
        );
        CREATE TABLE customers (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(120) NOT NULL, phone varchar(20) NOT NULL UNIQUE,
          email varchar(320), marketing_consent boolean NOT NULL DEFAULT false, order_count integer NOT NULL DEFAULT 0,
          lifetime_value bigint NOT NULL DEFAULT 0, last_order_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_customers_last_order ON customers(last_order_at);
        CREATE TABLE coupons (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code varchar(40) NOT NULL UNIQUE, description text,
          type discount_type NOT NULL, value integer NOT NULL CHECK (value > 0), minimum_subtotal integer NOT NULL DEFAULT 0,
          maximum_discount integer, usage_limit integer, usage_count integer NOT NULL DEFAULT 0,
          starts_at timestamptz, ends_at timestamptz, is_active boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
          CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at)
        );
        CREATE TABLE orders (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), order_number varchar(20) NOT NULL UNIQUE,
          public_token uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE, idempotency_key varchar(100) NOT NULL UNIQUE,
          customer_id uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
          status order_status NOT NULL DEFAULT 'pending', payment_method payment_method NOT NULL,
          payment_status payment_status NOT NULL DEFAULT 'pending', fulfillment_type fulfillment_type NOT NULL DEFAULT 'delivery',
          customer_name varchar(120) NOT NULL, customer_phone varchar(20) NOT NULL, customer_email varchar(320),
          delivery_address text, delivery_area varchar(100), delivery_instructions text,
          delivery_zone_id uuid REFERENCES delivery_zones(id) ON DELETE SET NULL,
          subtotal integer NOT NULL CHECK (subtotal >= 0), discount_total integer NOT NULL DEFAULT 0 CHECK (discount_total >= 0),
          tax_total integer NOT NULL DEFAULT 0 CHECK (tax_total >= 0), delivery_fee integer NOT NULL DEFAULT 0 CHECK (delivery_fee >= 0),
          total integer NOT NULL CHECK (total >= 0), coupon_id uuid REFERENCES coupons(id) ON DELETE SET NULL,
          coupon_code varchar(40), notes text, cancellation_reason text, confirmed_at timestamptz,
          delivered_at timestamptz, cancelled_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_orders_status_created ON orders(status, created_at DESC);
        CREATE INDEX ix_orders_customer ON orders(customer_id);
        CREATE TABLE order_items (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), order_id uuid NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
          product_id uuid REFERENCES products(id) ON DELETE SET NULL, product_name varchar(140) NOT NULL,
          quantity integer NOT NULL CHECK (quantity > 0), unit_price integer NOT NULL CHECK (unit_price >= 0),
          modifier_total integer NOT NULL DEFAULT 0, line_total integer NOT NULL CHECK (line_total >= 0),
          notes text, modifiers jsonb NOT NULL DEFAULT '[]', created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_order_items_order ON order_items(order_id);
        CREATE TABLE payments (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), order_id uuid NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
          provider varchar(40) NOT NULL, provider_reference varchar(200) UNIQUE, amount integer NOT NULL CHECK (amount > 0),
          status payment_status NOT NULL DEFAULT 'pending', metadata jsonb NOT NULL DEFAULT '{}', paid_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_payments_order ON payments(order_id);
        CREATE TABLE coupon_redemptions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), coupon_id uuid NOT NULL REFERENCES coupons(id) ON DELETE RESTRICT,
          customer_id uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
          order_id uuid NOT NULL REFERENCES orders(id) ON DELETE RESTRICT, amount integer NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE inventory_movements (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), ingredient_id uuid NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
          order_id uuid REFERENCES orders(id) ON DELETE SET NULL, type varchar(30) NOT NULL,
          quantity numeric(14,3) NOT NULL, reason text, actor_id uuid,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_inventory_movements_ingredient ON inventory_movements(ingredient_id, created_at DESC);
        CREATE TABLE refunds (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), order_id uuid NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
          payment_id uuid REFERENCES payments(id) ON DELETE SET NULL, amount integer NOT NULL CHECK (amount > 0),
          reason text NOT NULL, status refund_status NOT NULL DEFAULT 'requested', requested_by uuid NOT NULL,
          processed_by uuid, processed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE campaigns (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(140) NOT NULL, message text NOT NULL,
          channel varchar(30) NOT NULL DEFAULT 'whatsapp', audience jsonb NOT NULL DEFAULT '{}',
          status campaign_status NOT NULL DEFAULT 'draft', scheduled_at timestamptz, sent_at timestamptz,
          created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE notifications (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), order_id uuid REFERENCES orders(id) ON DELETE CASCADE,
          campaign_id uuid REFERENCES campaigns(id) ON DELETE CASCADE, channel varchar(30) NOT NULL,
          recipient varchar(320) NOT NULL, template varchar(100) NOT NULL, payload jsonb NOT NULL,
          status notification_status NOT NULL DEFAULT 'pending', attempts integer NOT NULL DEFAULT 0,
          next_attempt_at timestamptz NOT NULL DEFAULT now(), provider_reference varchar(200), last_error text, sent_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
          CHECK (order_id IS NOT NULL OR campaign_id IS NOT NULL)
        );
        CREATE INDEX ix_notifications_pending ON notifications(status, next_attempt_at);
        CREATE TABLE team_tasks (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), title varchar(180) NOT NULL, description text,
          status task_status NOT NULL DEFAULT 'todo', assigned_to uuid, due_at timestamptz, created_by uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE audit_logs (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), actor_id uuid, actor_email varchar(320), action varchar(120) NOT NULL,
          entity_type varchar(80) NOT NULL, entity_id varchar(100), before jsonb, after jsonb,
          ip_address varchar(80), user_agent text, request_id varchar(100), created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_audit_logs_entity ON audit_logs(entity_type, entity_id);
        CREATE INDEX ix_audit_logs_created ON audit_logs(created_at DESC);
        CREATE TABLE webhook_events (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), provider varchar(40) NOT NULL, event_id varchar(200) NOT NULL,
          event_type varchar(120) NOT NULL, payload jsonb NOT NULL, processed_at timestamptz, error text,
          created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(provider, event_id)
        );

        CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN NEW.updated_at = now(); RETURN NEW; END $$;
        DO $$ DECLARE table_name text; BEGIN
          FOREACH table_name IN ARRAY ARRAY['staff_profiles','store_settings','delivery_zones','categories','products','modifier_groups','modifier_options','ingredients','customers','coupons','orders','payments','refunds','campaigns','notifications','team_tasks']
          LOOP EXECUTE format('CREATE TRIGGER set_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_updated_at()', table_name); END LOOP;
        END $$;

        INSERT INTO store_settings(name, phone, email, address, opening_hours)
        VALUES ('Wrap Theory — Gulberg', '+923000000000', 'orders@example.com', 'Gulberg III, Lahore',
          '{"monday":{"open":"11:00","close":"01:00"},"tuesday":{"open":"11:00","close":"01:00"},"wednesday":{"open":"11:00","close":"01:00"},"thursday":{"open":"11:00","close":"01:00"},"friday":{"open":"11:00","close":"02:00"},"saturday":{"open":"11:00","close":"02:00"},"sunday":{"open":"11:00","close":"01:00"}}');
        INSERT INTO delivery_zones(name, areas, delivery_fee, minimum_order, free_delivery_threshold, estimated_minutes) VALUES
          ('Central Lahore', '["Gulberg","Gulberg I","Gulberg II","Gulberg III","Model Town","Garden Town"]', 15000, 50000, 250000, 35),
          ('Extended Lahore', '["DHA","DHA Phase 1","DHA Phase 2","DHA Phase 3","DHA Phase 4","Johar Town","Faisal Town"]', 25000, 75000, 300000, 50);

        WITH category AS (INSERT INTO categories(name, slug) VALUES ('Signature Wraps','signature-wraps') RETURNING id)
        INSERT INTO products(category_id,name,slug,description,price,tag,tone,is_featured,sort_order)
        SELECT id,'Smoky Theory','smoky-theory','Charred chicken, smoked cheddar, pickled onions & secret ember sauce',89000,'BESTSELLER','orange',true,1 FROM category
        UNION ALL SELECT id,'Green Thesis','green-thesis','Falafel, whipped feta, cucumber crunch, herbs & lemon tahini',76000,'PLANT POWER','green',true,2 FROM category
        UNION ALL SELECT id,'Seoul Searching','seoul-searching','Crispy chicken, kimchi slaw, sesame crunch & gochujang glaze',94000,'NEW DROP','red',true,3 FROM category
        UNION ALL SELECT id,'Custom Theory','custom-theory','Build your own wrap',69000,'THE LAB','orange',false,4 FROM category;

        INSERT INTO modifier_groups(name,min_selections,max_selections,sort_order) VALUES ('Protein',1,1,1),('Sauce',1,1,2);
        INSERT INTO modifier_options(group_id,name,price_delta,sort_order)
          SELECT id,'Smoky chicken',20000,1 FROM modifier_groups WHERE name='Protein'
          UNION ALL SELECT id,'Crispy beef',25000,2 FROM modifier_groups WHERE name='Protein'
          UNION ALL SELECT id,'Falafel',10000,3 FROM modifier_groups WHERE name='Protein'
          UNION ALL SELECT id,'Ember sauce',0,1 FROM modifier_groups WHERE name='Sauce'
          UNION ALL SELECT id,'Lemon tahini',0,2 FROM modifier_groups WHERE name='Sauce'
          UNION ALL SELECT id,'Gochujang',0,3 FROM modifier_groups WHERE name='Sauce';
        INSERT INTO product_modifier_groups(product_id,group_id)
          SELECT p.id,g.id FROM products p CROSS JOIN modifier_groups g WHERE p.slug='custom-theory';

        INSERT INTO ingredients(name,sku,unit,quantity_on_hand,reorder_level) VALUES
          ('Chicken portions','PROTEIN-CHICKEN','unit',200,30),('Falafel portions','PROTEIN-FALAFEL','unit',120,20),
          ('Beef portions','PROTEIN-BEEF','unit',100,20),('Tortillas','BASE-TORTILLA','unit',300,50);
        INSERT INTO product_ingredients(product_id,ingredient_id,quantity)
          SELECT p.id,i.id,1 FROM products p CROSS JOIN ingredients i WHERE i.sku='BASE-TORTILLA';
        INSERT INTO product_ingredients(product_id,ingredient_id,quantity)
          SELECT p.id,i.id,1 FROM products p JOIN ingredients i ON i.sku='PROTEIN-CHICKEN' WHERE p.slug IN ('smoky-theory','seoul-searching');
        INSERT INTO product_ingredients(product_id,ingredient_id,quantity)
          SELECT p.id,i.id,1 FROM products p JOIN ingredients i ON i.sku='PROTEIN-FALAFEL' WHERE p.slug='green-thesis';
        INSERT INTO modifier_option_ingredients(option_id,ingredient_id,quantity)
          SELECT o.id,i.id,1 FROM modifier_options o JOIN ingredients i ON
            (o.name='Smoky chicken' AND i.sku='PROTEIN-CHICKEN') OR
            (o.name='Crispy beef' AND i.sku='PROTEIN-BEEF') OR
            (o.name='Falafel' AND i.sku='PROTEIN-FALAFEL');

        -- The API owns all business data. Supabase browser roles cannot read or mutate it directly.
        DO $$ DECLARE table_name text; BEGIN
          FOREACH table_name IN ARRAY ARRAY['staff_profiles','store_settings','delivery_zones','categories','products','modifier_groups','modifier_options','product_modifier_groups','ingredients','product_ingredients','modifier_option_ingredients','customers','coupons','orders','order_items','payments','coupon_redemptions','inventory_movements','refunds','campaigns','notifications','team_tasks','audit_logs','webhook_events']
          LOOP
            EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
            EXECUTE format('REVOKE ALL ON TABLE %I FROM anon, authenticated', table_name);
          END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS webhook_events, audit_logs, team_tasks, notifications, campaigns, refunds,
          inventory_movements, coupon_redemptions, payments, order_items, orders, coupons, customers,
          modifier_option_ingredients, product_ingredients, ingredients, product_modifier_groups, modifier_options, modifier_groups,
          products, categories, delivery_zones, store_settings, staff_profiles CASCADE;
        DROP FUNCTION IF EXISTS set_updated_at();
        DROP SEQUENCE IF EXISTS order_number_seq;
        DROP TYPE IF EXISTS task_status, refund_status, notification_status, campaign_status, discount_type,
          fulfillment_type, payment_status, payment_method, order_status, staff_role;
        """
    )
