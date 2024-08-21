#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

use alloy_eips::{eip2930::AccessList, eip7702::SignedAuthorization};
use alloy_primitives::{Bytes, ChainId, TxKind, B256};

use crate::{
    transaction::eip4844::{TxEip4844, TxEip4844Variant, TxEip4844WithSidecar},
    Transaction, TxEip1559, TxEip2930, TxEip7702, TxEnvelope, TxLegacy, TxType,
};

/// The TypedTransaction enum represents all Ethereum transaction request types.
///
/// Its variants correspond to specific allowed transactions:
/// 1. Legacy (pre-EIP2718) [`TxLegacy`]
/// 2. EIP2930 (state access lists) [`TxEip2930`]
/// 3. EIP1559 [`TxEip1559`]
/// 4. EIP4844 [`TxEip4844Variant`]
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
#[cfg_attr(feature = "serde", derive(serde::Serialize, serde::Deserialize))]
#[cfg_attr(feature = "serde", serde(tag = "type"))]
#[doc(alias = "TypedTx", alias = "TxTyped", alias = "TransactionTyped")]
pub enum TypedTransaction {
    /// Legacy transaction
    #[cfg_attr(feature = "serde", serde(rename = "0x00", alias = "0x0"))]
    Legacy(TxLegacy),
    /// EIP-2930 transaction
    #[cfg_attr(feature = "serde", serde(rename = "0x01", alias = "0x1"))]
    Eip2930(TxEip2930),
    /// EIP-1559 transaction
    #[cfg_attr(feature = "serde", serde(rename = "0x02", alias = "0x2"))]
    Eip1559(TxEip1559),
    /// EIP-4844 transaction
    #[cfg_attr(feature = "serde", serde(rename = "0x03", alias = "0x3"))]
    Eip4844(TxEip4844Variant),
    /// EIP-7702 transaction
    #[cfg_attr(feature = "serde", serde(rename = "0x04", alias = "0x4"))]
    Eip7702(TxEip7702),
}

impl From<TxLegacy> for TypedTransaction {
    fn from(tx: TxLegacy) -> Self {
        Self::Legacy(tx)
    }
}

impl From<TxEip2930> for TypedTransaction {
    fn from(tx: TxEip2930) -> Self {
        Self::Eip2930(tx)
    }
}

impl From<TxEip1559> for TypedTransaction {
    fn from(tx: TxEip1559) -> Self {
        Self::Eip1559(tx)
    }
}

impl From<TxEip4844Variant> for TypedTransaction {
    fn from(tx: TxEip4844Variant) -> Self {
        Self::Eip4844(tx)
    }
}

impl From<TxEip4844> for TypedTransaction {
    fn from(tx: TxEip4844) -> Self {
        Self::Eip4844(tx.into())
    }
}

impl From<TxEip4844WithSidecar> for TypedTransaction {
    fn from(tx: TxEip4844WithSidecar) -> Self {
        Self::Eip4844(tx.into())
    }
}

impl From<TxEip7702> for TypedTransaction {
    fn from(tx: TxEip7702) -> Self {
        Self::Eip7702(tx)
    }
}

impl From<TxEnvelope> for TypedTransaction {
    fn from(envelope: TxEnvelope) -> Self {
        match envelope {
            TxEnvelope::Legacy(tx) => Self::Legacy(tx.strip_signature()),
            TxEnvelope::Eip2930(tx) => Self::Eip2930(tx.strip_signature()),
            TxEnvelope::Eip1559(tx) => Self::Eip1559(tx.strip_signature()),
            TxEnvelope::Eip4844(tx) => Self::Eip4844(tx.strip_signature()),
            TxEnvelope::Eip7702(tx) => Self::Eip7702(tx.strip_signature()),
        }
    }
}

impl TypedTransaction {
    /// Return the [`TxType`] of the inner txn.
    #[doc(alias = "transaction_type")]
    pub const fn tx_type(&self) -> TxType {
        match self {
            Self::Legacy(_) => TxType::Legacy,
            Self::Eip2930(_) => TxType::Eip2930,
            Self::Eip1559(_) => TxType::Eip1559,
            Self::Eip4844(_) => TxType::Eip4844,
            Self::Eip7702(_) => TxType::Eip7702,
        }
    }

    /// Return the inner legacy transaction if it exists.
    pub const fn legacy(&self) -> Option<&TxLegacy> {
        match self {
            Self::Legacy(tx) => Some(tx),
            _ => None,
        }
    }

    /// Return the inner EIP-2930 transaction if it exists.
    pub const fn eip2930(&self) -> Option<&TxEip2930> {
        match self {
            Self::Eip2930(tx) => Some(tx),
            _ => None,
        }
    }

    /// Return the inner EIP-1559 transaction if it exists.
    pub const fn eip1559(&self) -> Option<&TxEip1559> {
        match self {
            Self::Eip1559(tx) => Some(tx),
            _ => None,
        }
    }

    /// Return the inner EIP-7702 transaction if it exists.
    pub const fn eip7702(&self) -> Option<&TxEip7702> {
        match self {
            Self::Eip7702(tx) => Some(tx),
            _ => None,
        }
    }
}

impl Transaction for TypedTransaction {
    fn chain_id(&self) -> Option<ChainId> {
        match self {
            Self::Legacy(tx) => tx.chain_id(),
            Self::Eip2930(tx) => tx.chain_id(),
            Self::Eip1559(tx) => tx.chain_id(),
            Self::Eip4844(tx) => tx.chain_id(),
            Self::Eip7702(tx) => tx.chain_id(),
        }
    }

    fn nonce(&self) -> u64 {
        match self {
            Self::Legacy(tx) => tx.nonce(),
            Self::Eip2930(tx) => tx.nonce(),
            Self::Eip1559(tx) => tx.nonce(),
            Self::Eip4844(tx) => tx.nonce(),
            Self::Eip7702(tx) => tx.nonce(),
        }
    }

    fn gas_limit(&self) -> u128 {
        match self {
            Self::Legacy(tx) => tx.gas_limit(),
            Self::Eip2930(tx) => tx.gas_limit(),
            Self::Eip1559(tx) => tx.gas_limit(),
            Self::Eip4844(tx) => tx.gas_limit(),
            Self::Eip7702(tx) => tx.gas_limit(),
        }
    }

    fn gas_price(&self) -> Option<u128> {
        match self {
            Self::Legacy(tx) => tx.gas_price(),
            Self::Eip2930(tx) => tx.gas_price(),
            Self::Eip1559(tx) => tx.gas_price(),
            Self::Eip4844(tx) => tx.gas_price(),
            Self::Eip7702(tx) => tx.gas_price(),
        }
    }

    fn max_fee_per_gas(&self) -> u128 {
        match self {
            Self::Legacy(tx) => tx.max_fee_per_gas(),
            Self::Eip2930(tx) => tx.max_fee_per_gas(),
            Self::Eip1559(tx) => tx.max_fee_per_gas(),
            Self::Eip4844(tx) => tx.max_fee_per_gas(),
            Self::Eip7702(tx) => tx.max_fee_per_gas(),
        }
    }

    fn max_priority_fee_per_gas(&self) -> Option<u128> {
        match self {
            Self::Legacy(tx) => tx.max_priority_fee_per_gas(),
            Self::Eip2930(tx) => tx.max_priority_fee_per_gas(),
            Self::Eip1559(tx) => tx.max_priority_fee_per_gas(),
            Self::Eip4844(tx) => tx.max_priority_fee_per_gas(),
            Self::Eip7702(tx) => tx.max_priority_fee_per_gas(),
        }
    }

    fn priority_fee_or_price(&self) -> u128 {
        match self {
            Self::Legacy(tx) => tx.priority_fee_or_price(),
            Self::Eip2930(tx) => tx.priority_fee_or_price(),
            Self::Eip1559(tx) => tx.priority_fee_or_price(),
            Self::Eip4844(tx) => tx.priority_fee_or_price(),
            Self::Eip7702(tx) => tx.priority_fee_or_price(),
        }
    }

    fn max_fee_per_blob_gas(&self) -> Option<u128> {
        match self {
            Self::Legacy(tx) => tx.max_fee_per_blob_gas(),
            Self::Eip2930(tx) => tx.max_fee_per_blob_gas(),
            Self::Eip1559(tx) => tx.max_fee_per_blob_gas(),
            Self::Eip4844(tx) => tx.max_fee_per_blob_gas(),
            Self::Eip7702(tx) => tx.max_fee_per_blob_gas(),
        }
    }

    fn to(&self) -> TxKind {
        match self {
            Self::Legacy(tx) => tx.to(),
            Self::Eip2930(tx) => tx.to(),
            Self::Eip1559(tx) => tx.to(),
            Self::Eip4844(tx) => tx.to(),
            Self::Eip7702(tx) => tx.to(),
        }
    }

    fn value(&self) -> alloy_primitives::U256 {
        match self {
            Self::Legacy(tx) => tx.value(),
            Self::Eip2930(tx) => tx.value(),
            Self::Eip1559(tx) => tx.value(),
            Self::Eip4844(tx) => tx.value(),
            Self::Eip7702(tx) => tx.value(),
        }
    }

    fn input(&self) -> &Bytes {
        match self {
            Self::Legacy(tx) => tx.input(),
            Self::Eip2930(tx) => tx.input(),
            Self::Eip1559(tx) => tx.input(),
            Self::Eip4844(tx) => tx.input(),
            Self::Eip7702(tx) => tx.input(),
        }
    }

    fn ty(&self) -> u8 {
        match self {
            Self::Legacy(tx) => tx.ty(),
            Self::Eip2930(tx) => tx.ty(),
            Self::Eip1559(tx) => tx.ty(),
            Self::Eip4844(tx) => tx.ty(),
            Self::Eip7702(tx) => tx.ty(),
        }
    }

    fn access_list(&self) -> Option<&AccessList> {
        match self {
            Self::Legacy(tx) => tx.access_list(),
            Self::Eip2930(tx) => tx.access_list(),
            Self::Eip1559(tx) => tx.access_list(),
            Self::Eip4844(tx) => tx.access_list(),
            Self::Eip7702(tx) => tx.access_list(),
        }
    }

    fn blob_versioned_hashes(&self) -> Option<&[B256]> {
        match self {
            Self::Legacy(tx) => tx.blob_versioned_hashes(),
            Self::Eip2930(tx) => tx.blob_versioned_hashes(),
            Self::Eip1559(tx) => tx.blob_versioned_hashes(),
            Self::Eip4844(tx) => tx.blob_versioned_hashes(),
            Self::Eip7702(tx) => tx.blob_versioned_hashes(),
        }
    }

    fn authorization_list(&self) -> Option<&[SignedAuthorization]> {
        match self {
            Self::Legacy(tx) => tx.authorization_list(),
            Self::Eip2930(tx) => tx.authorization_list(),
            Self::Eip1559(tx) => tx.authorization_list(),
            Self::Eip4844(tx) => tx.authorization_list(),
            Self::Eip7702(tx) => tx.authorization_list(),
        }
    }
}

#[cfg(feature = "serde")]
impl<T: From<TypedTransaction>> From<TypedTransaction> for alloy_serde::WithOtherFields<T> {
    fn from(value: TypedTransaction) -> Self {
        Self::new(value.into())
    }
}

#[cfg(feature = "serde")]
impl<T: From<TxEnvelope>> From<TxEnvelope> for alloy_serde::WithOtherFields<T> {
    fn from(value: TxEnvelope) -> Self {
        Self::new(value.into())
    }
}
