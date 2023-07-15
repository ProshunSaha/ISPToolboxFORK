/// <reference types="cypress" />

describe("Test Access Your Information Flow", () => {
  beforeEach(() => {
    
  });

  it("Go through AYI Flow", function () {
    cy.login_fast();
    cy.visit("/pro/account/access/");
    
    cy.get("input[type=submit]").click();
    cy.contains('Loading').should('be.visible');
    cy.get('a').contains("Refresh to download").should('be.visible').click();
  });
});
