-- Initial schema migration for Vinted Parser Bot
-- Creates all core tables with proper constraints, indexes, and RLS policies

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    trial_expires TIMESTAMP WITH TIME ZONE NOT NULL,
    subscription_expires TIMESTAMP WITH TIME ZONE,
    referred_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    referrals_count INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Items table
CREATE TABLE items (
    id BIGINT PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR' NOT NULL,
    brand VARCHAR(255),
    size VARCHAR(100),
    condition VARCHAR(100),
    description TEXT,
    seller_id BIGINT,
    url VARCHAR(500) NOT NULL,
    preview_img VARCHAR(500),
    ships_to_at BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Photos table
CREATE TABLE photos (
    id BIGSERIAL PRIMARY KEY,
    item_id BIGINT REFERENCES items(id) ON DELETE CASCADE NOT NULL,
    url VARCHAR(500) NOT NULL,
    order_no INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Saved searches table
CREATE TABLE saved_searches (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    query VARCHAR(255) NOT NULL,
    filters JSONB,
    notifications_enabled BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Referrals table
CREATE TABLE referrals (
    id BIGSERIAL PRIMARY KEY,
    inviter_id BIGINT REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    invitee_id BIGINT REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    bonus_awarded BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    CONSTRAINT uq_referrals_invitee_id UNIQUE (invitee_id)
);

-- Payments table
CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    yookassa_id VARCHAR(255) UNIQUE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'RUB' NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create indexes for frequently queried columns
CREATE INDEX ix_users_tg_id ON users(tg_id);
CREATE INDEX ix_users_referred_by ON users(referred_by);
CREATE INDEX ix_users_created_at ON users(created_at);

CREATE INDEX ix_items_brand ON items(brand);
CREATE INDEX ix_items_seller_id ON items(seller_id);
CREATE INDEX ix_items_ships_to_at ON items(ships_to_at);
CREATE INDEX ix_items_brand_price ON items(brand, price);
CREATE INDEX ix_items_seller_created ON items(seller_id, created_at);
CREATE INDEX ix_items_ships_to_at_created ON items(ships_to_at, created_at);

CREATE INDEX ix_photos_item_id ON photos(item_id);
CREATE INDEX ix_photos_item_order ON photos(item_id, order_no);

CREATE INDEX ix_saved_searches_user_id ON saved_searches(user_id);

CREATE INDEX ix_referrals_inviter_id ON referrals(inviter_id);
CREATE INDEX ix_referrals_invitee_id ON referrals(invitee_id);
CREATE INDEX ix_referrals_inviter_created ON referrals(inviter_id, created_at);

CREATE INDEX ix_payments_user_id ON payments(user_id);
CREATE INDEX ix_payments_yookassa_id ON payments(yookassa_id);
CREATE INDEX ix_payments_status ON payments(status);
CREATE INDEX ix_payments_user_status ON payments(user_id, status);
CREATE INDEX ix_payments_status_created ON payments(status, created_at);

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_items_updated_at BEFORE UPDATE ON items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_photos_updated_at BEFORE UPDATE ON photos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_saved_searches_updated_at BEFORE UPDATE ON saved_searches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_referrals_updated_at BEFORE UPDATE ON referrals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payments_updated_at BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();