-- Enable Row Level Security (RLS) policies for data protection
-- This migration sets up security policies to protect user data

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE items ENABLE ROW LEVEL SECURITY;
ALTER TABLE photos ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE referrals ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- Users table policies
-- Users can only see their own data
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid()::text = id::text);

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid()::text = id::text);

-- Service role can manage all users (for bot operations)
CREATE POLICY "Service role can manage users" ON users
    FOR ALL USING (auth.role() = 'service_role');

-- Items table policies
-- Items are publicly readable but only service role can modify
CREATE POLICY "Items are publicly readable" ON items
    FOR SELECT USING (true);

CREATE POLICY "Service role can manage items" ON items
    FOR ALL USING (auth.role() = 'service_role');

-- Photos table policies
-- Photos are publicly readable but only service role can modify
CREATE POLICY "Photos are publicly readable" ON photos
    FOR SELECT USING (true);

CREATE POLICY "Service role can manage photos" ON photos
    FOR ALL USING (auth.role() = 'service_role');

-- Saved searches table policies
-- Users can only access their own saved searches
CREATE POLICY "Users can view own saved searches" ON saved_searches
    FOR SELECT USING (
        auth.uid()::text IN (
            SELECT id::text FROM users WHERE tg_id = (
                SELECT tg_id FROM users WHERE id::text = auth.uid()::text
            )
        )
    );

CREATE POLICY "Users can manage own saved searches" ON saved_searches
    FOR ALL USING (
        auth.uid()::text IN (
            SELECT id::text FROM users WHERE tg_id = (
                SELECT tg_id FROM users WHERE id::text = auth.uid()::text
            )
        )
    );

CREATE POLICY "Service role can manage saved searches" ON saved_searches
    FOR ALL USING (auth.role() = 'service_role');

-- Referrals table policies
-- Users can view referrals they're involved in
CREATE POLICY "Users can view own referrals" ON referrals
    FOR SELECT USING (
        auth.uid()::text IN (
            SELECT id::text FROM users WHERE id = inviter_id OR id = invitee_id
        )
    );

CREATE POLICY "Service role can manage referrals" ON referrals
    FOR ALL USING (auth.role() = 'service_role');

-- Payments table policies
-- Users can only see their own payments
CREATE POLICY "Users can view own payments" ON payments
    FOR SELECT USING (
        auth.uid()::text IN (
            SELECT id::text FROM users WHERE tg_id = (
                SELECT tg_id FROM users WHERE id::text = auth.uid()::text
            )
        )
    );

CREATE POLICY "Service role can manage payments" ON payments
    FOR ALL USING (auth.role() = 'service_role');

-- Create a function to get user ID from Telegram ID (for bot operations)
CREATE OR REPLACE FUNCTION get_user_id_by_tg_id(tg_user_id BIGINT)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    user_id BIGINT;
BEGIN
    SELECT id INTO user_id FROM users WHERE tg_id = tg_user_id;
    RETURN user_id;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION get_user_id_by_tg_id(BIGINT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_id_by_tg_id(BIGINT) TO service_role;