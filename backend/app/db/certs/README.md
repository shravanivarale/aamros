`supabase-prod-ca-2021.crt` is Supabase's PUBLIC root certificate ("Supabase Root 2021 CA", valid until 2031-04-26,
SHA-256 80:70:25:AD:50:D4:ED:21:9D:2C:9C:7D:29:9C:00:4F:82:4E:B0:0C:F7:F6:5A:FE:F6:07:D0:7B:72:E6:CA:FA), downloaded from
https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt (see Supabase docs: Database > SSL enforcement).
Supabase servers (direct and pooler) present a certificate chain that ends in this root, which Python's default trust store does not
contain, so connections are verified against this file (full chain + hostname check) instead of turning verification off.
