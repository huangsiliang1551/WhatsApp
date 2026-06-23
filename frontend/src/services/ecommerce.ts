export type EcommerceLookupSource = "api" | "frontend_mock";

export type EcommerceOrderItem = {
  sku: string;
  title: string;
  quantity: number;
  unit_price: number;
  currency: string;
};

export type EcommerceOrderShipment = {
  shipment_id: string;
  tracking_number: string;
  carrier: string;
  status: "pending" | "processing" | "in_transit" | "delivered";
  shipped_at: string | null;
  estimated_delivery_at: string | null;
};

export type EcommerceOrderDetail = {
  account_id: string;
  order_id: string;
  external_order_id: string;
  customer_id: string;
  customer_name: string;
  currency: string;
  payment_status: "pending" | "paid" | "refunded";
  fulfillment_status: "pending" | "processing" | "partial" | "shipped" | "delivered";
  total_amount: number;
  created_at: string;
  updated_at: string;
  shipping_address: string;
  items: EcommerceOrderItem[];
  shipments: EcommerceOrderShipment[];
};

export type EcommerceTrackingEvent = {
  status: string;
  location: string;
  description: string;
  occurred_at: string;
};

export type EcommerceTrackingDetail = {
  account_id: string;
  order_id: string;
  tracking_number: string;
  carrier: string;
  status: "pending" | "processing" | "in_transit" | "delivered";
  estimated_delivery_at: string | null;
  recipient_name: string;
  destination: string;
  events: EcommerceTrackingEvent[];
};

export type EcommerceOrderLookupResult = {
  source: EcommerceLookupSource;
  data: EcommerceOrderDetail;
};

export type EcommerceTrackingLookupResult = {
  source: EcommerceLookupSource;
  data: EcommerceTrackingDetail;
};

export type EcommerceMockExample = {
  label: string;
  account_id: string;
  order_id: string;
  tracking_number: string;
};

export const MOCK_ORDERS: EcommerceOrderDetail[] = [
  {
    account_id: "demo-account-es",
    order_id: "MOCK-1001",
    external_order_id: "SHOP-ES-9001",
    customer_id: "customer-es-1",
    customer_name: "Sofia Alvarez",
    currency: "USD",
    payment_status: "paid",
    fulfillment_status: "shipped",
    total_amount: 129.5,
    created_at: "2026-06-04T08:30:00Z",
    updated_at: "2026-06-05T03:10:00Z",
    shipping_address: "Calle Mayor 18, Madrid, ES",
    items: [
      {
        sku: "SKU-BAG-01",
        title: "Travel Tote",
        quantity: 1,
        unit_price: 79.5,
        currency: "USD"
      },
      {
        sku: "SKU-STRAP-02",
        title: "Canvas Shoulder Strap",
        quantity: 1,
        unit_price: 50,
        currency: "USD"
      }
    ],
    shipments: [
      {
        shipment_id: "ship-es-1001",
        tracking_number: "YTES123456789",
        carrier: "YunTrack Express",
        status: "in_transit",
        shipped_at: "2026-06-04T14:45:00Z",
        estimated_delivery_at: "2026-06-08T12:00:00Z"
      }
    ]
  },
  {
    account_id: "demo-account-fr",
    order_id: "MOCK-2001",
    external_order_id: "SHOP-FR-4410",
    customer_id: "customer-fr-1",
    customer_name: "Camille Martin",
    currency: "EUR",
    payment_status: "paid",
    fulfillment_status: "processing",
    total_amount: 88,
    created_at: "2026-06-03T09:12:00Z",
    updated_at: "2026-06-06T01:20:00Z",
    shipping_address: "15 Rue de Rivoli, Paris, FR",
    items: [
      {
        sku: "SKU-LAMP-07",
        title: "Desk Lamp",
        quantity: 1,
        unit_price: 58,
        currency: "EUR"
      },
      {
        sku: "SKU-BULB-02",
        title: "Warm LED Bulb",
        quantity: 2,
        unit_price: 15,
        currency: "EUR"
      }
    ],
    shipments: [
      {
        shipment_id: "ship-fr-2001",
        tracking_number: "FRPOST987654321",
        carrier: "La Poste",
        status: "processing",
        shipped_at: null,
        estimated_delivery_at: "2026-06-09T16:00:00Z"
      }
    ]
  },
  {
    account_id: "demo-account-ar",
    order_id: "MOCK-3001",
    external_order_id: "SHOP-AR-7712",
    customer_id: "customer-ar-1",
    customer_name: "Omar Hassan",
    currency: "AED",
    payment_status: "paid",
    fulfillment_status: "delivered",
    total_amount: 245,
    created_at: "2026-05-29T11:00:00Z",
    updated_at: "2026-06-02T06:30:00Z",
    shipping_address: "Sheikh Zayed Road, Dubai, AE",
    items: [
      {
        sku: "SKU-WATCH-03",
        title: "Sport Watch",
        quantity: 1,
        unit_price: 245,
        currency: "AED"
      }
    ],
    shipments: [
      {
        shipment_id: "ship-ar-3001",
        tracking_number: "ARAMEX556677889",
        carrier: "Aramex",
        status: "delivered",
        shipped_at: "2026-05-30T07:00:00Z",
        estimated_delivery_at: "2026-06-02T18:00:00Z"
      }
    ]
  }
];

const MOCK_TRACKING: EcommerceTrackingDetail[] = [
  {
    account_id: "demo-account-es",
    order_id: "MOCK-1001",
    tracking_number: "YTES123456789",
    carrier: "YunTrack Express",
    status: "in_transit",
    estimated_delivery_at: "2026-06-08T12:00:00Z",
    recipient_name: "Sofia Alvarez",
    destination: "Madrid, ES",
    events: [
      {
        status: "label_created",
        location: "Shenzhen, CN",
        description: "Shipping label created by warehouse.",
        occurred_at: "2026-06-04T09:20:00Z"
      },
      {
        status: "departed_origin",
        location: "Shenzhen, CN",
        description: "Parcel departed export facility.",
        occurred_at: "2026-06-04T16:40:00Z"
      },
      {
        status: "arrived_hub",
        location: "Madrid, ES",
        description: "Parcel arrived at destination hub.",
        occurred_at: "2026-06-05T22:15:00Z"
      }
    ]
  },
  {
    account_id: "demo-account-fr",
    order_id: "MOCK-2001",
    tracking_number: "FRPOST987654321",
    carrier: "La Poste",
    status: "processing",
    estimated_delivery_at: "2026-06-09T16:00:00Z",
    recipient_name: "Camille Martin",
    destination: "Paris, FR",
    events: [
      {
        status: "payment_confirmed",
        location: "Paris, FR",
        description: "Order paid and queued for packing.",
        occurred_at: "2026-06-03T09:20:00Z"
      },
      {
        status: "packing",
        location: "Lyon, FR",
        description: "Warehouse is packing the order.",
        occurred_at: "2026-06-06T01:20:00Z"
      }
    ]
  },
  {
    account_id: "demo-account-ar",
    order_id: "MOCK-3001",
    tracking_number: "ARAMEX556677889",
    carrier: "Aramex",
    status: "delivered",
    estimated_delivery_at: "2026-06-02T18:00:00Z",
    recipient_name: "Omar Hassan",
    destination: "Dubai, AE",
    events: [
      {
        status: "picked_up",
        location: "Dubai, AE",
        description: "Courier picked up the parcel.",
        occurred_at: "2026-05-30T08:10:00Z"
      },
      {
        status: "out_for_delivery",
        location: "Dubai, AE",
        description: "Courier is out for delivery.",
        occurred_at: "2026-06-02T09:05:00Z"
      },
      {
        status: "delivered",
        location: "Dubai, AE",
        description: "Recipient signed for the parcel.",
        occurred_at: "2026-06-02T15:42:00Z"
      }
    ]
  }
];

export const ECOMMERCE_MOCK_EXAMPLES: EcommerceMockExample[] = [
  {
    label: "西语订单",
    account_id: "demo-account-es",
    order_id: "MOCK-1001",
    tracking_number: "YTES123456789"
  },
  {
    label: "法语订单",
    account_id: "demo-account-fr",
    order_id: "MOCK-2001",
    tracking_number: "FRPOST987654321"
  },
  {
    label: "阿语订单",
    account_id: "demo-account-ar",
    order_id: "MOCK-3001",
    tracking_number: "ARAMEX556677889"
  }
];

export function findMockOrderDetail(
  accountId: string,
  orderId: string
): EcommerceOrderDetail | null {
  const normalizedAccountId = accountId.trim().toLowerCase();
  const normalizedOrderId = orderId.trim().toLowerCase();

  return (
    MOCK_ORDERS.find(
      (order) =>
        order.account_id.toLowerCase() === normalizedAccountId &&
        order.order_id.toLowerCase() === normalizedOrderId
    ) ?? null
  );
}

export function findMockTrackingDetail(
  accountId: string,
  trackingNumber: string
): EcommerceTrackingDetail | null {
  const normalizedAccountId = accountId.trim().toLowerCase();
  const normalizedTrackingNumber = trackingNumber.trim().toLowerCase();

  return (
    MOCK_TRACKING.find(
      (tracking) =>
        tracking.account_id.toLowerCase() === normalizedAccountId &&
        tracking.tracking_number.toLowerCase() === normalizedTrackingNumber
    ) ?? null
  );
}
