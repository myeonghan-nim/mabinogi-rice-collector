package core

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
)

const apiEndpoint = "https://open.api.nexon.com/mabinogi/v1/auction/keyword-search"

var (
	ErrUnauthorized      = errors.New("API 키 인증 실패")
	ErrNotEnoughListings = errors.New("경매장 데이터 부족")
)

// Client는 넥슨 Open API 클라이언트다.
type Client struct {
	APIKey  string
	BaseURL string
	HTTP    *http.Client
}

func NewClient(apiKey string) *Client {
	return &Client{
		APIKey:  apiKey,
		BaseURL: apiEndpoint,
		HTTP:    &http.Client{Timeout: 10 * time.Second},
	}
}

type auctionItem struct {
	ItemDisplayName     string `json:"item_display_name"`
	AuctionPricePerUnit int64  `json:"auction_price_per_unit"`
}

type searchResponse struct {
	AuctionItem []auctionItem `json:"auction_item"`
	Error       *struct {
		Name    string `json:"name"`
		Message string `json:"message"`
	} `json:"error"`
}

// FetchLowestTwo는 표시 이름에 검색어가 포함된 매물 중 최저가와 차순위가를 돌려준다.
// Python 원본과 동일하게 첫 응답 페이지만 사용한다.
func (c *Client) FetchLowestTwo(ctx context.Context, keyword string) (lowest, next int64, err error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		c.BaseURL+"?"+url.Values{"keyword": {keyword}}.Encode(), nil)
	if err != nil {
		return 0, 0, err
	}
	req.Header.Set("accept", "application/json")
	req.Header.Set("x-nxopen-api-key", c.APIKey)

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return 0, 0, err
	}
	defer resp.Body.Close()

	var body searchResponse
	decodeErr := json.NewDecoder(resp.Body).Decode(&body)

	if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
		return 0, 0, ErrUnauthorized
	}
	if resp.StatusCode != http.StatusOK {
		msg := ""
		if body.Error != nil {
			msg = " " + body.Error.Name + ": " + body.Error.Message
		}
		return 0, 0, fmt.Errorf("API 요청 실패: %d%s", resp.StatusCode, msg)
	}
	if decodeErr != nil {
		return 0, 0, fmt.Errorf("응답 파싱 실패: %w", decodeErr)
	}

	items := body.AuctionItem
	sort.Slice(items, func(i, j int) bool {
		return items[i].AuctionPricePerUnit < items[j].AuctionPricePerUnit
	})
	prices := make([]int64, 0, 2)
	for _, it := range items {
		if strings.Contains(it.ItemDisplayName, keyword) {
			prices = append(prices, it.AuctionPricePerUnit)
			if len(prices) == 2 {
				break
			}
		}
	}
	if len(prices) < 2 {
		return 0, 0, fmt.Errorf("%w: %d개 발견 (2개 필요)", ErrNotEnoughListings, len(prices))
	}
	return prices[0], prices[1], nil
}
