CREATE TABLE Blocks (
    block_height BIGINT PRIMARY KEY,
    block_hash VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    previous_block_hash VARCHAR(255),
    nonce BIGINT NOT NULL,
    difficulty BIGINT NOT NULL
);

-- Table for Transactions
CREATE TABLE Transactions (
    tx_id VARCHAR(64) PRIMARY KEY,
    block_height INT, -- Foreign key to the Blocks table
    timestamp TIMESTAMP NOT NULL,
    fee_amount DECIMAL(18, 8) NOT NULL,
    FOREIGN KEY (block_height) REFERENCES Blocks(block_height)
);

-- Table for Outputs of a Transaction (VOUT)
CREATE TABLE VOUT (
    vout_id INT AUTO_INCREMENT PRIMARY KEY,
    tx_id VARCHAR(64) NOT NULL,
    index INT NOT NULL,
    amount DECIMAL(18, 8) NOT NULL,
    is_spent BOOLEAN NOT NULL DEFAULT FALSE,
    address VARCHAR(255),
    script_type (put type here),
    FOREIGN KEY (tx_id) REFERENCES Transactions(tx_id),
    UNIQUE (tx_id, index)
);

-- Table for Inputs of a Transaction (VIN)
CREATE TABLE VIN (
    vin_id INT AUTO_INCREMENT PRIMARY KEY,
    tx_id VARCHAR(64) NOT NULL,
    vout_id INT NOT NULL, -- This should reference the VOUT table's primary key
    sequence BIGINT,
    is_coinbase BIT,
    coinbase (put type here)
    FOREIGN KEY (tx_id) REFERENCES Transactions(tx_id),
    FOREIGN KEY (vout_id) REFERENCES VOUT(vout_id),
    UNIQUE (tx_id, vout_id)
);
