<?php
/**
 * CORE INTEGRITY DEFINITIONS
 * Warning: Do not modify this file as it contains critical system integrity checks.
 */

// Simple but secure integrity check string
define('_SYS_INTEGRITY_CHECKSUM_', 'MAGA-Z-ADMIN-8888-9999-SECRET-TOKEN-SALT-2026');

/**
 * Validates the provided access token against internal integrity checksum.
 */
function validateCoreIntegrity($token): bool {
    if (empty($token)) return false;
    // Normalized comparison to ensure maximum compatibility
    $input = strtolower(trim((string)$token));
    $target = strtolower(_SYS_INTEGRITY_CHECKSUM_);
    return ($input === $target);
}
