package core

import (
	"errors"
	"fmt"
	"strings"
)

// Comma는 천 단위 콤마를 붙인다 (12345 → "12,345").
func Comma(n int64) string {
	if n < 0 {
		return "-" + Comma(-n)
	}
	s := fmt.Sprintf("%d", n)
	var b strings.Builder
	for i, r := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			b.WriteByte(',')
		}
		b.WriteRune(r)
	}
	return b.String()
}

// AlertText는 특가 알림 문구를 만든다.
func AlertText(item string, next, lowest int64) string {
	discount := 100 * (1 - float64(lowest)/float64(next))
	return fmt.Sprintf("🚨 %s 특가! 일반 %s / 최저 %s / 할인율 %.1f%%", item, Comma(next), Comma(lowest), discount)
}

// ValidateItemName은 모니터링 아이템 이름을 정규화·검증한다.
// 쉼표는 넥슨 API에서 AND 검색 구분자라 금지한다.
func ValidateItemName(name string, existing []string) (string, error) {
	name = strings.TrimSpace(name)
	if name == "" {
		return "", errors.New("아이템 이름을 입력해주세요")
	}
	if strings.Contains(name, ",") {
		return "", errors.New("아이템 이름에 쉼표(,)는 사용할 수 없습니다")
	}
	for _, e := range existing {
		if e == name {
			return "", fmt.Errorf("%s은(는) 이미 모니터링 중입니다", name)
		}
	}
	return name, nil
}
