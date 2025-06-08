"""
Encryption module for Suhana.

This module provides functions for encrypting and decrypting sensitive data.
"""

import base64
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionManager:
    """
    Manages encryption and decryption of sensitive data.

    This class provides methods for encrypting and decrypting data using
    Fernet symmetric encryption, with key derivation from a password.
    Supports key rotation for enhanced security.
    """

    def __init__(self, key_file: Optional[Path] = None, password: Optional[str] = None,
                 key_rotation_days: int = 90, reencrypt_dirs: List[Path] = None):
        """
        Initialize the encryption manager.

        Args:
            key_file: Path to the key file (optional)
            password: Password for key derivation (optional)
            key_rotation_days: Number of days after which keys should be rotated (default: 90)
            reencrypt_dirs: List of directories to reencrypt after key rotation (default: None)

        If neither key_file nor password is provided, a new key will be generated
        and stored in the default location.
        """
        self.logger = logging.getLogger(__name__)
        self.keys_dir = Path("config") / "encryption_keys"
        self.key_file = key_file or self.keys_dir / "current_keys.json"
        self.key_rotation_days = key_rotation_days
        self.reencrypt_dirs = reencrypt_dirs
        self.keys = []  # List of (key, timestamp) tuples
        self.fernet = None
        self.multi_fernet = None

        # Ensure the keys directory exists
        self.keys_dir.mkdir(exist_ok=True, parents=True)

        if password:
            # Derive key from password
            self._derive_key(password)
        elif self.key_file.exists():
            # Load keys from file
            self._load_keys()
        else:
            # Generate new key
            self._generate_key()

        # Check if key rotation is needed
        self._check_key_rotation(reencrypt_dirs)

        # Initialize MultiFernet with all active keys
        self._initialize_fernet()

    def _derive_key(self, password: str) -> None:
        """
        Derive encryption key from password.

        Args:
            password: Password for key derivation
        """
        try:
            # Use a fixed salt for reproducibility
            # In a production environment, this should be stored securely
            salt = b'suhana_encryption_salt'

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )

            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            timestamp = datetime.now().isoformat()

            # Add the new key as the primary key
            self.keys = [(key, timestamp)] + self.keys

            # Save keys to file
            self._save_keys()

            # Initialize Fernet instances
            self._initialize_fernet()

            self.logger.info("Derived new encryption key from password")
        except Exception as e:
            self.logger.error(f"Error deriving key from password: {e}")
            raise

    def _generate_key(self) -> None:
        """
        Generate a new encryption key and save it to the key file.
        """
        try:
            key = Fernet.generate_key()
            timestamp = datetime.now().isoformat()

            # Add the new key as the primary key
            self.keys = [(key, timestamp)] + self.keys

            # Save keys to file
            self._save_keys()

            # Initialize Fernet instances
            self._initialize_fernet()

            self.logger.info("Generated new encryption key")
        except Exception as e:
            self.logger.error(f"Error generating encryption key: {e}")
            raise

    def _save_keys(self) -> None:
        """
        Save encryption keys to the key file.
        """
        try:
            # Convert keys to serializable format
            serialized_keys = [
                {
                    "key": base64.b64encode(key).decode(),
                    "timestamp": timestamp
                }
                for key, timestamp in self.keys
            ]

            # Save to file
            with open(self.key_file, "w") as f:
                json.dump(serialized_keys, f)

            self.logger.info(f"Saved encryption keys to {self.key_file}")
        except Exception as e:
            self.logger.error(f"Error saving encryption keys: {e}")
            raise

    def _load_keys(self) -> None:
        """
        Load encryption keys from the key file.
        """
        try:
            with open(self.key_file, "r") as f:
                serialized_keys = json.load(f)

            # Convert from serializable format
            self.keys = [
                (base64.b64decode(key_data["key"]), key_data["timestamp"])
                for key_data in serialized_keys
            ]

            # Initialize Fernet instances
            self._initialize_fernet()

            self.logger.info(f"Loaded {len(self.keys)} encryption keys from {self.key_file}")
        except Exception as e:
            self.logger.error(f"Error loading encryption keys: {e}")
            # If there's an error loading keys, generate a new one
            self._generate_key()

    def _initialize_fernet(self) -> None:
        """
        Initialize Fernet and MultiFernet instances with the current keys.
        """
        if not self.keys:
            self._generate_key()
            return

        try:
            # The first key is the primary key for encryption
            self.fernet = Fernet(self.keys[0][0])

            # All keys are used for decryption, in order
            fernet_instances = [Fernet(key) for key, _ in self.keys]
            self.multi_fernet = MultiFernet(fernet_instances)
        except Exception as e:
            self.logger.error(f"Error initializing Fernet instances: {e}")
            raise

    def _check_key_rotation(self, reencrypt_dirs: List[Path] = None) -> None:
        """
        Check if key rotation is needed and rotate keys if necessary.

        Args:
            reencrypt_dirs: List of directories to reencrypt after key rotation (default: None)
        """
        if not self.keys:
            return

        try:
            # Check if the primary key is older than the rotation period
            primary_key_timestamp = datetime.fromisoformat(self.keys[0][1])
            rotation_threshold = datetime.now() - timedelta(days=self.key_rotation_days)

            if primary_key_timestamp < rotation_threshold:
                self.logger.info("Key rotation needed - primary key has expired")
                self.rotate_keys(reencrypt_dirs=reencrypt_dirs)
        except Exception as e:
            self.logger.error(f"Error checking key rotation: {e}")
            # Continue with existing keys

    def rotate_keys(self, max_keys: int = 5, reencrypt_dirs: List[Path] = None) -> None:
        """
        Rotate encryption keys by generating a new primary key.

        Args:
            max_keys: Maximum number of keys to keep (default: 5)
            reencrypt_dirs: List of directories to reencrypt after key rotation (default: None)
        """
        try:
            # Generate a new key
            new_key = Fernet.generate_key()
            timestamp = datetime.now().isoformat()

            # Add the new key as the primary key
            self.keys = [(new_key, timestamp)] + self.keys

            # Keep only the specified number of keys
            if len(self.keys) > max_keys:
                self.keys = self.keys[:max_keys]

            # Save keys to file
            self._save_keys()

            # Reinitialize Fernet instances
            self._initialize_fernet()

            self.logger.info(f"Rotated encryption keys, now using {len(self.keys)} keys")

            # Reencrypt files in specified directories
            if reencrypt_dirs:
                total_success = 0
                total_files = 0

                for directory in reencrypt_dirs:
                    self.logger.info(f"Reencrypting files in {directory}")
                    success, total = self.reencrypt_directory(directory)
                    total_success += success
                    total_files += total

                self.logger.info(f"Reencryption after key rotation: {total_success}/{total_files} files successfully reencrypted")
        except Exception as e:
            self.logger.error(f"Error rotating encryption keys: {e}")
            raise

    def encrypt(self, data: Union[str, bytes, Dict[str, Any]]) -> bytes:
        """
        Encrypt data.

        Args:
            data: Data to encrypt (string, bytes, or dictionary)

        Returns:
            bytes: Encrypted data
        """
        try:
            if self.fernet is None:
                raise ValueError("Encryption key not initialized")

            # Convert data to bytes
            if isinstance(data, dict):
                data_bytes = json.dumps(data).encode()
            elif isinstance(data, str):
                data_bytes = data.encode()
            else:
                data_bytes = data

            # Encrypt data
            encrypted_data = self.fernet.encrypt(data_bytes)
            return encrypted_data
        except Exception as e:
            self.logger.error(f"Error encrypting data: {e}")
            raise

    def decrypt(self, encrypted_data: bytes) -> Union[str, Dict[str, Any]]:
        """
        Decrypt data.

        Args:
            encrypted_data: Encrypted data

        Returns:
            Union[str, Dict[str, Any]]: Decrypted data
        """
        try:
            if self.multi_fernet is None:
                raise ValueError("Encryption keys not initialized")

            # Decrypt data using MultiFernet to try all available keys
            decrypted_bytes = self.multi_fernet.decrypt(encrypted_data)

            # Try to parse as JSON
            try:
                return json.loads(decrypted_bytes.decode())
            except json.JSONDecodeError:
                # Return as string if not valid JSON
                return decrypted_bytes.decode()
        except Exception as e:
            self.logger.error(f"Error decrypting data: {e}")
            raise

    def encrypt_file(self, file_path: Path) -> Path:
        """
        Encrypt a file.

        Args:
            file_path: Path to the file to encrypt

        Returns:
            Path: Path to the encrypted file
        """
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Read file content
            with open(file_path, "rb") as f:
                file_data = f.read()

            # Encrypt data
            encrypted_data = self.encrypt(file_data)

            # Write encrypted data to file
            encrypted_file_path = file_path.with_suffix(file_path.suffix + ".enc")
            with open(encrypted_file_path, "wb") as f:
                f.write(encrypted_data)

            return encrypted_file_path
        except Exception as e:
            self.logger.error(f"Error encrypting file {file_path}: {e}")
            raise

    def decrypt_file(self, encrypted_file_path: Path) -> Path:
        """
        Decrypt a file.

        Args:
            encrypted_file_path: Path to the encrypted file

        Returns:
            Path: Path to the decrypted file
        """
        try:
            if not encrypted_file_path.exists():
                raise FileNotFoundError(f"File not found: {encrypted_file_path}")

            # Read encrypted file content
            with open(encrypted_file_path, "rb") as f:
                encrypted_data = f.read()

            # Decrypt data using the decrypt method which now uses multi_fernet
            decrypted_data = self.decrypt(encrypted_data)

            # Determine output file path
            if encrypted_file_path.suffix == ".enc":
                decrypted_file_path = encrypted_file_path.with_suffix("")
            else:
                decrypted_file_path = encrypted_file_path.with_suffix(encrypted_file_path.suffix + ".dec")

            # Write decrypted data to file
            with open(decrypted_file_path, "wb") as f:
                if isinstance(decrypted_data, str):
                    f.write(decrypted_data.encode())
                elif isinstance(decrypted_data, dict):
                    import json
                    f.write(json.dumps(decrypted_data).encode("utf-8"))
                else:
                    f.write(decrypted_data)

            return decrypted_file_path
        except Exception as e:
            self.logger.error(f"Error decrypting file {encrypted_file_path}: {e}")
            raise

    def reencrypt_file(self, file_path: Path) -> bool:
        """
        Re-encrypt a file with the current primary key.

        This is useful after key rotation to ensure all files are encrypted
        with the newest key.

        Args:
            file_path: Path to the encrypted file

        Returns:
            bool: True if re-encryption successful, False otherwise
        """
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Decrypt file using multi_fernet (via decrypt_file)
            decrypted_file_path = self.decrypt_file(file_path)

            # Re-encrypt file with the primary key
            encrypted_file_path = self.encrypt_file(decrypted_file_path)

            # Replace original file
            os.replace(encrypted_file_path, file_path)

            # Remove temporary decrypted file
            os.remove(decrypted_file_path)

            self.logger.info(f"Successfully re-encrypted file {file_path} with the primary key")
            return True
        except Exception as e:
            self.logger.error(f"Error re-encrypting file {file_path}: {e}")
            return False

    def reencrypt_directory(self, directory_path: Path, file_pattern: str = "*.enc") -> Tuple[int, int]:
        """
        Re-encrypt all encrypted files in a directory with the current primary key.

        This is useful after key rotation to ensure all files are encrypted
        with the newest key.

        Args:
            directory_path: Path to the directory containing encrypted files
            file_pattern: Pattern to match encrypted files (default: "*.enc")

        Returns:
            Tuple[int, int]: (number of successfully re-encrypted files, total number of files)
        """
        try:
            if not directory_path.exists() or not directory_path.is_dir():
                raise NotADirectoryError(f"Directory not found: {directory_path}")

            # Find all encrypted files
            encrypted_files = list(directory_path.glob(file_pattern))
            total_files = len(encrypted_files)

            if total_files == 0:
                self.logger.info(f"No encrypted files found in {directory_path}")
                return 0, 0

            # Re-encrypt each file
            success_count = 0
            for file_path in encrypted_files:
                try:
                    if self.reencrypt_file(file_path):
                        success_count += 1
                except Exception as e:
                    self.logger.error(f"Error re-encrypting file {file_path}: {e}")
                    # Continue with next file

            self.logger.info(f"Re-encrypted {success_count}/{total_files} files in {directory_path}")
            return success_count, total_files
        except Exception as e:
            self.logger.error(f"Error re-encrypting directory {directory_path}: {e}")
            return 0, 0


# Convenience functions

def encrypt_sensitive_data(data: Dict[str, Any], sensitive_fields: list) -> Dict[str, Any]:
    """
    Encrypt sensitive fields in a dictionary.

    Args:
        data: Dictionary containing data
        sensitive_fields: List of field names to encrypt

    Returns:
        Dict[str, Any]: Dictionary with sensitive fields encrypted
    """
    try:
        # Create encryption manager
        encryption_manager = EncryptionManager()

        # Create a copy of the data
        encrypted_data = data.copy()

        # Encrypt sensitive fields
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field] is not None:
                # Encrypt field
                encrypted_value = encryption_manager.encrypt(encrypted_data[field])
                # Store as base64 string for easier storage
                encrypted_data[field] = base64.b64encode(encrypted_value).decode()
                # Mark field as encrypted
                encrypted_data[f"{field}_encrypted"] = True

        return encrypted_data
    except Exception as e:
        logging.error(f"Error encrypting sensitive data: {e}")
        return data


def decrypt_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt sensitive fields in a dictionary.

    Args:
        data: Dictionary containing data with encrypted fields

    Returns:
        Dict[str, Any]: Dictionary with sensitive fields decrypted
    """
    try:
        # Create encryption manager
        encryption_manager = EncryptionManager()

        # Create a copy of the data
        decrypted_data = data.copy()

        # Find and decrypt encrypted fields
        encrypted_fields = [field[:-10] for field in data.keys() if field.endswith("_encrypted") and data[field]]

        for field in encrypted_fields:
            if field in decrypted_data and decrypted_data[field] is not None:
                # Decode from base64
                encrypted_value = base64.b64decode(decrypted_data[field])
                # Decrypt field
                decrypted_data[field] = encryption_manager.decrypt(encrypted_value)
                # Remove encryption marker
                decrypted_data.pop(f"{field}_encrypted", None)

        return decrypted_data
    except Exception as e:
        logging.error(f"Error decrypting sensitive data: {e}")
        return data
